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

# Ensure directories exist
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
    # Indexes for lightning-fast queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON media(source)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON media(date_taken)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_camera ON media(camera_model)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_location ON media(location_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON media(original_name)")
    conn.commit()
    conn.close()

def get_rich_metadata(file_path, file_type):
    """Extracts extensive metadata from both images and videos."""
    meta = {
        "date_taken": None, "camera_model": None, 
        "width": None, "height": None, "f_stop": None,
        "exposure_time": None, "iso": None, "flash_fired": None,
        "lat": None, "lon": None
    }
    
    if file_type == "document":
        return meta

    # --- VIDEO PROCESSING ---
    if file_type == "video":
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(file_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)
            
            if "format" in data and "tags" in data["format"]:
                tags = {k.lower(): v for k, v in data["format"]["tags"].items()}
                
                # Extract Date
                raw_date = tags.get("creation_time")
                if raw_date:
                    meta["date_taken"] = raw_date.replace("T", " ")[:19]
                
                # Extract Camera Model (Expanded to catch iOS and alternate Android formats)
                meta["camera_model"] = tags.get("model") or tags.get("com.android.model") or tags.get("com.apple.quicktime.model")
                
                # NEW: Extract GPS from ISO 6709 string (e.g., +12.9716+077.5946/)
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

    if file_type == "image":
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
    """Generates and caches a thumbnail during the organization phase."""
    path_hash = hashlib.md5(str(file_path).encode('utf-8')).hexdigest()
    cache_path = THUMB_DIR / f"{path_hash}.jpg"
    
    if cache_path.exists():
        return # Already done

    try:
        if file_type == "image":
            with Image.open(file_path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail((400, 400))
                img.save(cache_path, "JPEG", quality=75)
        
        elif file_type == "video":
            cmd = [
                "ffmpeg", "-y", "-i", str(file_path), 
                "-ss", "00:00:00.100", "-vframes", "1", 
                "-vf", "scale=400:-1", str(cache_path)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception as e:
        print(f"Could not generate thumbnail for {file_path}: {e}")


def process_staging():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
    video_exts = {'.mp4', '.mkv', '.mov', '.avi'}
    doc_exts = {'.pdf', '.docx', '.txt', '.xlsx', '.csv'}
    files_processed = 0

    for source_name, folder_path in STAGING_DIRS.items():
        for file_path in folder_path.rglob("*"):
            if file_path.is_dir(): continue

            # --- NEW: ZERO-COST DEDUPLICATION CHECK ---
            cursor.execute("SELECT 1 FROM media WHERE original_name = ?", (file_path.name,))
            if cursor.fetchone():
                duplicates_skipped += 1
                continue # Instantly skips to the next file, leaving this one in staging
            # ------------------------------------------
                
            ext = file_path.suffix.lower()
            if ext not in image_exts and ext not in video_exts and ext not in doc_exts: continue
                
            if ext in image_exts: file_type = "image"
            elif ext in video_exts: file_type = "video"
            else: file_type = "document"
            
            # Extract Data
            m = get_rich_metadata(file_path, file_type)
            parsed_date = get_fallback_date(file_path, m["date_taken"])
            
            # Target Path Logic
            target_dir = ORGANIZED_DIR / parsed_date.strftime("%Y") / parsed_date.strftime("%m")
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Compress and move
            final_target_path = compress_and_move(file_path, target_dir, file_path.name, file_type, ext)
            generate_thumbnail(final_target_path, file_type)
            new_size_kb = round(os.path.getsize(final_target_path) / 1024, 2)
            
            # Offline Geocoding
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
            
            # Insert into DB
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
            files_processed += 1

    conn.commit()
    conn.close()
    print(f"Organized and indexed {files_processed} files.")

if __name__ == "__main__":
    init_db()
    process_staging()
