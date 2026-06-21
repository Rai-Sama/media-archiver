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
    # Add Facial Recognition Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER,
            encoding BLOB,
            cluster_id INTEGER,
            person_name TEXT,
            FOREIGN KEY(media_id) REFERENCES media(id)
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

def get_rich_metadata(file_path, file_type, ext):
    meta = {
        "date_taken": None, "camera_model": None, 
        "width": None, "height": None, "f_stop": None,
        "exposure_time": None, "iso": None, "flash_fired": None,
        "lat": None, "lon": None
    }
    
    if file_type in ["document", "audio"]:
        return meta

    # --- RAW PROCESSING ---
    if ext in ['.dng', '.cr2', '.nef', '.arw']:
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                if "EXIF DateTimeOriginal" in tags:
                    meta["date_taken"] = str(tags["EXIF DateTimeOriginal"])
                if "Image Model" in tags:
                    meta["camera_model"] = str(tags["Image Model"]).strip()
        except Exception:
            pass
        return meta

    # --- VIDEO PROCESSING ---
    if file_type == "video":
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(file_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)
            
            if "format" in data and "tags" in data["format"]:
                tags = {k.lower(): v for k, v in data["format"]["tags"].items()}
                
                raw_date = tags.get("creation_time")
                if raw_date:
                    meta["date_taken"] = raw_date.replace("T", " ")[:19]
                
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
        except Exception:
            pass 
        return meta

    # --- IMAGE PROCESSING ---
    try:
        with Image.open(file_path) as img:
            meta["width"] = img.width
            meta["height"] = img.height
            
            exif = img._getexif()
            if not exif:
                return meta
            
            exif_data = {TAGS.get(k, k): v for k, v in exif.items()}
            
            meta["camera_model"] = str(exif_data.get("Model", "")).strip() or None
            meta["iso"] = exif_data.get("ISOSpeedRatings")
            meta["flash_fired"] = 1 if exif_data.get("Flash") in [1, 9, 25, 73, 89] else 0
            
            if "FNumber" in exif_data:
                meta["f_stop"] = float(exif_data["FNumber"])
            if "ExposureTime" in exif_data:
                meta["exposure_time"] = str(exif_data["ExposureTime"])
                
            if "DateTimeOriginal" in exif_data:
                meta["date_taken"] = exif_data["DateTimeOriginal"]
            elif "DateTime" in exif_data:
                meta["date_taken"] = exif_data["DateTime"]

            if "GPSInfo" in exif_data:
                gps_info = {GPSTAGS.get(k, k): v for k, v in exif_data["GPSInfo"].items()}
                def get_deg(val): return float(val[0]) + (float(val[1])/60.0) + (float(val[2])/3600.0)
                
                if "GPSLatitude" in gps_info and "GPSLatitudeRef" in gps_info:
                    meta["lat"] = get_deg(gps_info["GPSLatitude"]) * (1 if gps_info["GPSLatitudeRef"] == "N" else -1)
                if "GPSLongitude" in gps_info and "GPSLongitudeRef" in gps_info:
                    meta["lon"] = get_deg(gps_info["GPSLongitude"]) * (1 if gps_info["GPSLongitudeRef"] == "E" else -1)
    except Exception:
        pass 
    
    return meta

def get_fallback_date(file_path, exif_date_str):
    if exif_date_str:
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(exif_date_str, fmt)
            except ValueError:
                continue
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
                else:
                    rgb_im = img.convert('RGB')
                
                exif = img.info.get('exif')
                if exif:
                    rgb_im.save(new_target, "JPEG", quality=75, optimize=True, exif=exif)
                else:
                    rgb_im.save(new_target, "JPEG", quality=75, optimize=True)
            
            os.remove(source_path) 
            return new_target
        except Exception:
            os.rename(source_path, target_path)
            return target_path

    elif file_type == "video":
        new_target = target_path.with_suffix('.mp4')
        cmd = [
            "ffmpeg", "-y", "-i", str(source_path), 
            "-map_metadata", "0", 
            "-c:v", "libx265", "-crf", "28", "-preset", "medium", 
            "-c:a", "aac", "-b:a", "128k", "-async", "1",
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
    
    if cache_path.exists():
        return cache_path

    try:
        if file_type == "image":
            with Image.open(file_path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail((400, 400))
                img.save(cache_path, "JPEG", quality=75)
            return cache_path
        
        elif file_type == "video":
            cmd = [
                "ffmpeg", "-y", "-i", str(file_path), 
                "-ss", "00:00:00.100", "-vframes", "1", 
                "-vf", "scale=400:-1", str(cache_path)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return cache_path
    except Exception:
        return None


def extract_faces(media_id, thumbnail_path, cursor):
    if not thumbnail_path or not thumbnail_path.exists():
        return
        
    try:
        image = face_recognition.load_image_file(str(thumbnail_path))
        
        # 1. Find the physical locations (bounding boxes) of the faces
        face_locations = face_recognition.face_locations(image)
        # 2. Extract the math vectors based on those exact locations
        face_encodings = face_recognition.face_encodings(image, known_face_locations=face_locations)
        
        # 3. Save both the vector and the box to the database
        for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
            encoding_blob = encoding.tobytes()
            cursor.execute("""
                INSERT INTO faces (media_id, encoding, box_top, box_right, box_bottom, box_left) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (media_id, encoding_blob, top, right, bottom, left))
            
    except Exception as e:
        print(f"Face extraction failed for ID {media_id}: {e}")


def process_staging():
    print("--- Starting Media Pipeline ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
    raw_exts = {'.dng', '.cr2', '.nef', '.arw'}
    video_exts = {'.mp4', '.mkv', '.mov', '.avi'}
    doc_exts = {'.pdf', '.docx', '.txt', '.xlsx', '.csv'}
    audio_exts = {'.mp3', '.m4a', '.wav', '.aac', '.ogg'}
    
    files_processed = 0
    duplicates_skipped = 0

    for source_name, folder_path in STAGING_DIRS.items():
        for file_path in folder_path.rglob("*"):
            if file_path.is_dir(): continue

            cursor.execute("SELECT 1 FROM media WHERE original_name = ?", (file_path.name,))
            if cursor.fetchone():
                duplicates_skipped += 1
                continue 
                
            ext = file_path.suffix.lower()
            valid_exts = image_exts | raw_exts | video_exts | doc_exts | audio_exts
            if ext not in valid_exts: 
                continue
                
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
            
            location_str = None
            if m["lat"] is not None and m["lon"] is not None:
                try:
                    geo_result = rg.search((m["lat"], m["lon"]))
                    if geo_result:
                        city = geo_result[0].get('name', '')
                        state = geo_result[0].get('admin1', '')
                        location_str = f"{city}, {state}".strip(", ")
                except Exception:
                    pass
            
            cursor.execute("""
                INSERT OR REPLACE INTO media 
                (original_name, current_path, file_type, source, date_taken, 
                file_size_kb, width, height, camera_model, f_stop, exposure_time, 
                iso, flash_fired, latitude, longitude, location_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_path.name, str(final_target_path), file_type, source_name, 
                parsed_date.strftime("%Y-%m-%d %H:%M:%S"), new_size_kb, 
                m["width"], m["height"], m["camera_model"], m["f_stop"], 
                m["exposure_time"], m["iso"], m["flash_fired"], m["lat"], m["lon"], location_str
            ))
            
            media_id = cursor.lastrowid
            
            if thumbnail_path:
                extract_faces(media_id, thumbnail_path, cursor)
                
            files_processed += 1

    conn.commit()
    conn.close()
    
    print(f"Organized and indexed {files_processed} files.")
    if duplicates_skipped > 0:
        print(f"Skipped {duplicates_skipped} exact name duplicates (left safely in staging).")

def cluster_faces():
    """Runs DBSCAN to cluster all facial vectors in the database."""
    print("\n--- Running Facial Clustering ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, encoding FROM faces WHERE is_manual = 0 AND encoding IS NOT NULL")
    rows = cursor.fetchall()

    if not rows:
        print("No faces found in the database to cluster.")
        conn.close()
        return

    face_ids = []
    encodings = []

    for row_id, blob in rows:
        try:
            encoding = np.frombuffer(blob, dtype=np.float64)
            face_ids.append(row_id)
            encodings.append(encoding)
        except Exception:
            pass

    if not encodings:
        print("No valid encodings found.")
        conn.close()
        return

    print(f"Running DBSCAN algorithm on {len(encodings)} faces...")
    
    # eps=0.45 is strict enough to prevent false matches, loose enough to catch different angles
    clt = DBSCAN(metric="euclidean", n_jobs=-1, eps=0.45, min_samples=3)
    clt.fit(encodings)

    cluster_ids = clt.labels_
    
    unique_clusters = len(set(cluster_ids)) - (1 if -1 in cluster_ids else 0)
    print(f"Success! Grouped faces into {unique_clusters} distinct people.")

    print("Saving cluster assignments to the database...")
    updates = [(int(cid), fid) for fid, cid in zip(face_ids, cluster_ids)]
    cursor.executemany("UPDATE faces SET cluster_id = ? WHERE id = ?", updates)
    
    conn.commit()
    conn.close()
    print("Pipeline Complete! Ready for UI interaction.")

if __name__ == "__main__":
    init_db()
    process_staging()
    # Execute the clustering instantly after the staging queue is processed
    cluster_faces()
