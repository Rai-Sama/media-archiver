import os
import sqlite3
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS
from pillow_heif import register_heif_opener
import subprocess
import json
import reverse_geocoder as rg
import re
import hashlib
import rawpy
import exifread
import face_recognition
import numpy as np
from sklearn.cluster import DBSCAN
import concurrent.futures
import tempfile

# Register HEIC opener with Pillow
register_heif_opener()

# Configuration
BASE_DIR = Path.home() / "everything/personal/backup"
STAGING_DIRS = {
    "me": BASE_DIR / "staging" / "me",
    "shared": BASE_DIR / "staging" / "shared",
    "misc": BASE_DIR / "staging" / "misc"
}
ORGANIZED_DIR = BASE_DIR / "organized"
DB_PATH = BASE_DIR / "media_index.db"

THUMB_DIR = BASE_DIR / ".thumbnails"
THUMB_DIR.mkdir(parents=True, exist_ok=True)

for path in STAGING_DIRS.values():
    path.mkdir(parents=True, exist_ok=True)
ORGANIZED_DIR.mkdir(parents=True, exist_ok=True)

GEO_CACHE = {}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT,
            current_path TEXT UNIQUE,
            file_type TEXT,
            source TEXT,
            date_taken TEXT,
            file_size_kb REAL,
            width INTEGER,
            height INTEGER,
            camera_model TEXT,
            f_stop REAL,
            exposure_time TEXT,
            iso INTEGER,
            flash_fired INTEGER,
            latitude REAL,
            longitude REAL,
            location_name TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER,
            encoding BLOB,
            cluster_id INTEGER,
            person_name TEXT,
            exclude_from_ml INTEGER DEFAULT 0,
            box_top INTEGER,
            box_right INTEGER,
            box_bottom INTEGER,
            box_left INTEGER,
            FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON media(source)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON media(date_taken)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_camera ON media(camera_model)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_location ON media(location_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON media(original_name)")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_id ON faces(media_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_person_name ON faces(person_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cluster_id ON faces(cluster_id)")
    
    conn.commit()
    conn.close()

def get_location_name(lat, lon):
    if lat is None or lon is None: return None
    key = (round(lat, 3), round(lon, 3))
    if key in GEO_CACHE:
        return GEO_CACHE[key]
    
    try:
        geo_result = rg.search((lat, lon))
        if geo_result:
            city = geo_result[0].get('name', '')
            state = geo_result[0].get('admin1', '')
            loc_str = f"{city}, {state}".strip(", ")
            GEO_CACHE[key] = loc_str
            return loc_str
    except Exception:
        pass
    return None

def get_rich_metadata(file_path, file_type, ext):
    meta = {
        "date_taken": None, "camera_model": None, 
        "width": None, "height": None, "f_stop": None,
        "exposure_time": None, "iso": None, "flash_fired": None,
        "lat": None, "lon": None
    }
    
    if file_type in ["document", "audio"]: return meta

    if ext in ['.dng', '.cr2', '.nef', '.arw']:
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                if "EXIF DateTimeOriginal" in tags: meta["date_taken"] = str(tags["EXIF DateTimeOriginal"])
                if "Image Model" in tags: meta["camera_model"] = str(tags["Image Model"]).strip()
        except Exception: pass
        return meta

    if file_type == "video":
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(file_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)
            
            if "format" in data and "tags" in data["format"]:
                tags = {k.lower(): v for k, v in data["format"]["tags"].items()}
                raw_date = tags.get("creation_time")
                if raw_date: meta["date_taken"] = raw_date.replace("T", " ")[:19]
                meta["camera_model"] = tags.get("model") or tags.get("com.android.model") or tags.get("com.apple.quicktime.model")
                
                location_str = tags.get("location") or tags.get("location-eng")
                if location_str:
                    match = re.search(r'([+-]\d+\.\d+)([+-]\d+\.\d+)', location_str)
                    if match:
                        meta["lat"] = float(match.group(1))
                        meta["lon"] = float(match.group(2))
                
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    meta["width"] = stream.get("width")
                    meta["height"] = stream.get("height")
                    break
        except Exception: pass 
        return meta

    try:
        with Image.open(file_path) as img:
            meta["width"] = img.width
            meta["height"] = img.height
            
            exif = img._getexif()
            if not exif: return meta
            
            exif_data = {TAGS.get(k, k): v for k, v in exif.items()}
            
            meta["camera_model"] = str(exif_data.get("Model", "")).strip() or None
            meta["iso"] = exif_data.get("ISOSpeedRatings")
            meta["flash_fired"] = 1 if exif_data.get("Flash") in [1, 9, 25, 73, 89] else 0
            
            if "FNumber" in exif_data: meta["f_stop"] = float(exif_data["FNumber"])
            if "ExposureTime" in exif_data: meta["exposure_time"] = str(exif_data["ExposureTime"])
            if "DateTimeOriginal" in exif_data: meta["date_taken"] = exif_data["DateTimeOriginal"]
            elif "DateTime" in exif_data: meta["date_taken"] = exif_data["DateTime"]

            if "GPSInfo" in exif_data:
                gps_info = {GPSTAGS.get(k, k): v for k, v in exif_data["GPSInfo"].items()}
                def get_deg(val): return float(val[0]) + (float(val[1])/60.0) + (float(val[2])/3600.0)
                
                if "GPSLatitude" in gps_info and "GPSLatitudeRef" in gps_info:
                    meta["lat"] = get_deg(gps_info["GPSLatitude"]) * (1 if gps_info["GPSLatitudeRef"] == "N" else -1)
                if "GPSLongitude" in gps_info and "GPSLongitudeRef" in gps_info:
                    meta["lon"] = get_deg(gps_info["GPSLongitude"]) * (1 if gps_info["GPSLongitudeRef"] == "E" else -1)
    except Exception: pass 
    return meta

def get_fallback_date(file_path, exif_date_str):
    if exif_date_str:
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try: return datetime.strptime(exif_date_str, fmt)
            except ValueError: continue
    return datetime.fromtimestamp(file_path.stat().st_mtime)

def compress_and_move(source_path, target_dir, original_name, file_type, ext):
    target_path = target_dir / original_name
    counter = 1
    while target_path.exists():
        target_path = target_dir / f"{source_path.stem}_{counter}{ext}"
        counter += 1

    if ext in ['.dng', '.cr2', '.nef', '.arw']:
        new_target = target_path.with_suffix('.jpg')
        while new_target.exists():
            new_target = target_dir / f"{source_path.stem}_{counter}.jpg"
            counter += 1
            
        try:
            with rawpy.imread(str(source_path)) as raw:
                rgb = raw.postprocess(use_camera_wb=True)
                Image.fromarray(rgb).save(new_target, "JPEG", quality=75, optimize=True)
            os.remove(source_path)
            return new_target
        except Exception:
            os.rename(source_path, target_path)
            return target_path

    elif file_type == "image":
        try:
            with Image.open(source_path) as img:
                if getattr(img, "is_animated", False):
                    os.rename(source_path, target_path)
                    return target_path

                new_target = target_path.with_suffix('.jpg')
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.convert('RGBA').split()[3])
                    rgb_im = background
                else: rgb_im = img.convert('RGB')
                
                exif = img.info.get('exif')
                if exif: rgb_im.save(new_target, "JPEG", quality=75, optimize=True, exif=exif)
                else: rgb_im.save(new_target, "JPEG", quality=75, optimize=True)
            
            os.remove(source_path) 
            return new_target
        except Exception:
            os.rename(source_path, target_path)
            return target_path

    elif file_type == "video":
        new_target = target_path.with_suffix('.mp4')
        # FIXED: Restricted FFmpeg wrapper AND restricted the libx265 internal encoder pool
        cmd = [
            "ffmpeg", "-y", "-i", str(source_path), 
            "-map_metadata", "0", 
            "-c:v", "libx265", "-crf", "28", "-preset", "medium", 
            "-x265-params", "pools=1",
            "-c:a", "aac", "-b:a", "128k", "-async", "1",
            "-threads", "1",
            "-v", "quiet", str(new_target)
        ]
        try:
            subprocess.run(cmd, check=True)
            os.remove(source_path)
            return new_target
        except subprocess.CalledProcessError:
            os.rename(source_path, target_path)
            return target_path
    else:
        os.rename(source_path, target_path)
        return target_path

def generate_thumbnail(file_path, file_type):
    path_hash = hashlib.md5(str(file_path).encode('utf-8')).hexdigest()
    cache_path = THUMB_DIR / f"{path_hash}.jpg"
    if cache_path.exists(): return cache_path

    try:
        if file_type == "image":
            with Image.open(file_path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != 'RGB': img = img.convert('RGB')
                img.thumbnail((400, 400))
                img.save(cache_path, "JPEG", quality=75)
            return cache_path
        
        elif file_type == "video":
            cmd = [
                "ffmpeg", "-y", "-i", str(file_path), 
                "-ss", "00:00:00.100", "-vframes", "1", 
                "-vf", "scale=400:-1", "-threads", "1", str(cache_path)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return cache_path
    except Exception: return None

def extract_faces_worker(final_target_path, file_type, thumb_path):
    extracted_faces = []
    if not thumb_path or not thumb_path.exists(): return extracted_faces
        
    try:
        with Image.open(thumb_path) as t_img:
            thumb_w, thumb_h = t_img.size

        img_array = None
        ml_w, ml_h = 0, 0
        temp_path = None

        if file_type == "image":
            with Image.open(final_target_path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != 'RGB': img = img.convert('RGB')
                
                orig_w, orig_h = img.size
                scale = min(1200 / orig_w, 1200 / orig_h)
                if scale > 1: scale = 1 
                
                ml_img = img.resize((int(orig_w * scale), int(orig_h * scale)), Image.Resampling.LANCZOS)
                ml_w, ml_h = ml_img.size
                img_array = np.array(ml_img)
                
        elif file_type == "video":
            with tempfile.NamedTemporaryFile(suffix=".jpg", dir=BASE_DIR, delete=False) as tf:
                temp_path = tf.name
                
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(final_target_path),
                    "-ss", "00:00:00.100", "-vframes", "1",
                    "-vf", "scale='min(1200,iw)':-1", "-threads", "1", temp_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                
                if Path(temp_path).exists():
                    with Image.open(temp_path) as img:
                        ml_w, ml_h = img.size
                        img_array = np.array(img)
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

        if img_array is not None:
            face_locations = face_recognition.face_locations(img_array)
            face_encodings = face_recognition.face_encodings(img_array, known_face_locations=face_locations)
            
            if ml_w > 0:
                ratio = thumb_w / ml_w
                for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
                    extracted_faces.append({
                        "encoding": encoding.tobytes(),
                        "box_top": int(top * ratio),
                        "box_right": int(right * ratio),
                        "box_bottom": int(bottom * ratio),
                        "box_left": int(left * ratio)
                    })
                    
    except Exception as e:
        print(f"Face extraction failed: {e}")
        
    return extracted_faces

def process_single_file_worker(args):
    file_path, source_name = args
    ext = file_path.suffix.lower()
    
    image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
    raw_exts = {'.dng', '.cr2', '.nef', '.arw'}
    video_exts = {'.mp4', '.mkv', '.mov', '.avi'}
    doc_exts = {'.pdf', '.docx', '.doc', '.txt', '.xlsx', '.csv', '.ppt', '.pptx'}
    audio_exts = {'.mp3', '.m4a', '.wav', '.aac', '.ogg'}
    
    if ext in image_exts: file_type = "image"
    elif ext in raw_exts: file_type = "image"
    elif ext in video_exts: file_type = "video"
    elif ext in audio_exts: file_type = "audio"
    else: file_type = "document"
    
    m = get_rich_metadata(file_path, file_type, ext)
    
    if file_type == "video":
        for img_ext in ['.heic', '.jpg', '.jpeg']:
            potential_match = file_path.with_suffix(img_ext)
            if potential_match.exists():
                m_photo = get_rich_metadata(potential_match, "image", img_ext)
                if m_photo.get("date_taken"): m["date_taken"] = m_photo["date_taken"]
                if m_photo.get("lat"): 
                    m["lat"] = m_photo["lat"]
                    m["lon"] = m_photo["lon"]
                if m_photo.get("camera_model"): m["camera_model"] = m_photo["camera_model"]
                break
    
    parsed_date = get_fallback_date(file_path, m["date_taken"])
    target_dir = ORGANIZED_DIR / parsed_date.strftime("%Y") / parsed_date.strftime("%m")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    final_target_path = compress_and_move(file_path, target_dir, file_path.name, file_type, ext)
    
    thumbnail_path = None
    if file_type in ["image", "video"]:
        thumbnail_path = generate_thumbnail(final_target_path, file_type)
        
    new_size_kb = round(os.path.getsize(final_target_path) / 1024, 2)
    location_str = get_location_name(m["lat"], m["lon"])
            
    faces_data = []
    if thumbnail_path:
        faces_data = extract_faces_worker(final_target_path, file_type, thumbnail_path)

    return {
        "original_name": file_path.name,
        "current_path": str(final_target_path),
        "file_type": file_type,
        "source": source_name,
        "date_taken": parsed_date.strftime("%Y-%m-%d %H:%M:%S"),
        "file_size_kb": new_size_kb,
        "width": m["width"],
        "height": m["height"],
        "camera_model": m["camera_model"],
        "f_stop": m["f_stop"],
        "exposure_time": m["exposure_time"],
        "iso": m["iso"],
        "flash_fired": m["flash_fired"],
        "latitude": m["lat"],
        "longitude": m["lon"],
        "location_name": location_str,
        "faces": faces_data
    }

def process_staging():
    print("--- Starting Parallel Media Pipeline ---")
    
    # Open DB, fetch names, and IMMEDIATELY CLOSE IT to prevent POSIX lock inheritance
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT original_name FROM media")
    existing_names = {row[0] for row in cursor.fetchall()}
    conn.close() 
    
    image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
    raw_exts = {'.dng', '.cr2', '.nef', '.arw'}
    video_exts = {'.mp4', '.mkv', '.mov', '.avi'}
    doc_exts = {'.pdf', '.docx', '.doc', '.txt', '.xlsx', '.csv', '.ppt', '.pptx'}
    audio_exts = {'.mp3', '.m4a', '.wav', '.aac', '.ogg'}
    valid_exts = image_exts | raw_exts | video_exts | doc_exts | audio_exts
    
    queued_names = set()
    all_tasks = []
    duplicates_skipped = 0

    for source_name, folder_path in STAGING_DIRS.items():
        for file_path in folder_path.rglob("*"):
            if file_path.is_dir() or file_path.suffix.lower() not in valid_exts:
                continue
            
            if file_path.name in existing_names or file_path.name in queued_names:
                duplicates_skipped += 1
                continue
                
            queued_names.add(file_path.name)
            all_tasks.append((file_path, source_name))

    total_tasks = len(all_tasks)
    print(f"Found {total_tasks} new files to process. (Skipped {duplicates_skipped} duplicates).")
    
    if total_tasks == 0:
        return

    files_processed = 0
    CHUNK_SIZE = 500
    task_chunks = [all_tasks[i:i + CHUNK_SIZE] for i in range(0, total_tasks, CHUNK_SIZE)]

    max_w = min(4, os.cpu_count() or 1)
    print(f"Spinning up {max_w} worker processes... (CPU usage will spike safely)")
    
    for chunk_idx, chunk in enumerate(task_chunks, 1):
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_w) as executor:
            future_to_file = {executor.submit(process_single_file_worker, task): task for task in chunk}
            
            # The workers are done spawning, so it is safe to open the DB exclusively in the main thread
            conn = sqlite3.connect(DB_PATH, timeout=15.0) 
            cursor = conn.cursor()
            
            for future in concurrent.futures.as_completed(future_to_file):
                try:
                    result = future.result()
                    
                    cursor.execute("""
                        INSERT INTO media 
                        (original_name, current_path, file_type, source, date_taken, 
                        file_size_kb, width, height, camera_model, f_stop, exposure_time, 
                        iso, flash_fired, latitude, longitude, location_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        result["original_name"], result["current_path"], result["file_type"], 
                        result["source"], result["date_taken"], result["file_size_kb"], 
                        result["width"], result["height"], result["camera_model"], result["f_stop"], 
                        result["exposure_time"], result["iso"], result["flash_fired"], 
                        result["latitude"], result["longitude"], result["location_name"]
                    ))
                    
                    media_id = cursor.lastrowid
                    
                    for face in result["faces"]:
                        cursor.execute("""
                            INSERT INTO faces (media_id, encoding, box_top, box_right, box_bottom, box_left, exclude_from_ml) 
                            VALUES (?, ?, ?, ?, ?, ?, 0)
                        """, (
                            media_id, face["encoding"], face["box_top"], face["box_right"], 
                            face["box_bottom"], face["box_left"]
                        ))
                    
                    files_processed += 1
                    
                    if files_processed % 10 == 0:
                        conn.commit()
                        print(f"[{files_processed}/{total_tasks}] Indexed batch...")
                        
                except Exception as exc:
                    print(f"File generated an exception: {exc}")

            conn.commit()
            conn.close() 

    print(f"Parallel pipeline finished. Successfully indexed {files_processed} files.")

def cluster_faces():
    """Runs a semi-supervised clustering sweep using known anchors to prevent chaining."""
    print("\n--- Running Smart Facial Clustering ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Gather Known Anchors (Faces you have already manually tagged)
    cursor.execute("SELECT person_name, encoding FROM faces WHERE person_name IS NOT NULL AND exclude_from_ml = 0 AND encoding IS NOT NULL")
    known_rows = cursor.fetchall()

    anchors = {}
    for name, blob in known_rows:
        try:
            enc = np.frombuffer(blob, dtype=np.float64)
            if name not in anchors:
                anchors[name] = []
            anchors[name].append(enc)
        except Exception: 
            pass

    # Create an average 128-d vector profile for each known person
    anchor_profiles = {}
    for name, encs in anchors.items():
        anchor_profiles[name] = np.mean(encs, axis=0)

    # 2. Fetch Unknown Faces
    cursor.execute("SELECT id, encoding FROM faces WHERE person_name IS NULL AND exclude_from_ml = 0 AND encoding IS NOT NULL")
    unknown_rows = cursor.fetchall()

    if not unknown_rows:
        print("No unknown faces to cluster.")
        conn.close()
        return

    unknown_ids = []
    unknown_encs = []
    for row_id, blob in unknown_rows:
        try:
            unknown_ids.append(row_id)
            unknown_encs.append(np.frombuffer(blob, dtype=np.float64))
        except Exception: 
            pass

    # 3. Match Unknowns to Anchors First
    print(f"Comparing {len(unknown_encs)} unknown faces against {len(anchor_profiles)} known profiles...")
    leftover_ids = []
    leftover_encs = []
    matches_found = 0

    for f_id, enc in zip(unknown_ids, unknown_encs):
        best_match_name = None
        best_distance = 0.42 # Strict distance threshold for a guaranteed match

        for name, profile in anchor_profiles.items():
            dist = np.linalg.norm(profile - enc) # Euclidean distance
            if dist < best_distance:
                best_distance = dist
                best_match_name = name

        if best_match_name:
            # Auto-tag the face and remove it from the clustering pool (-1)
            cursor.execute("UPDATE faces SET person_name = ?, cluster_id = -1 WHERE id = ?", (best_match_name, f_id))
            matches_found += 1
        else:
            leftover_ids.append(f_id)
            leftover_encs.append(enc)

    print(f"Auto-tagged {matches_found} faces based on your manual tags.")

    # 4. Run stricter DBSCAN on the leftovers
    if leftover_encs:
        print(f"Running strict DBSCAN on the remaining {len(leftover_encs)} unknown faces...")
        # eps reduced to 0.38 to prevent the "Mega-Cluster" chaining effect. min_samples raised to 4.
        clt = DBSCAN(metric="euclidean", n_jobs=-1, eps=0.38, min_samples=4)
        clt.fit(leftover_encs)

        cluster_ids = clt.labels_
        unique_clusters = len(set(cluster_ids)) - (1 if -1 in cluster_ids else 0)
        print(f"Grouped remaining faces into {unique_clusters} new unknown clusters.")

        updates = [(int(cid), fid) for fid, cid in zip(leftover_ids, cluster_ids)]
        cursor.executemany("UPDATE faces SET cluster_id = ? WHERE id = ?", updates)

    conn.commit()
    conn.close()
    print("Pipeline Complete! Ready for UI interaction.")

if __name__ == "__main__":
    init_db()
    process_staging()
    cluster_faces()
