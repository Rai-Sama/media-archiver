import sqlite3
from pathlib import Path
import os
import hashlib
import face_recognition
import numpy as np
from PIL import Image, ImageOps
import reverse_geocoder as rg

from organize import get_rich_metadata, generate_thumbnail, DB_PATH, ORGANIZED_DIR, THUMB_DIR, BASE_DIR, get_fallback_date

GEO_CACHE = {}

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

def reconcile_database():
    print("--- Starting Full Database Reconciliation ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT current_path FROM media")
    tracked_paths = {row[0] for row in cursor.fetchall()}
    
    image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.heic'}
    video_exts = {'.mp4', '.mkv', '.mov', '.avi'}
    doc_exts = {'.pdf', '.docx', '.doc', '.txt', '.xlsx', '.csv', '.ppt', '.pptx'}
    audio_exts = {'.mp3', '.m4a', '.wav', '.aac', '.ogg'}
    valid_exts = image_exts | video_exts | doc_exts | audio_exts

    missing_files = []

    print("Scanning organized directory for ghost files...")
    for file_path in ORGANIZED_DIR.rglob("*"):
        if file_path.is_dir() or file_path.suffix.lower() not in valid_exts:
            continue
            
        if str(file_path) not in tracked_paths:
            missing_files.append(file_path)

    if not missing_files:
        print("Database is perfectly synced with your hard drive. No ghost files found.")
        conn.close()
        return

    print(f"Found {len(missing_files)} ghost files. Re-indexing metadata and faces now...\n")

    files_recovered = 0
    faces_recovered = 0

    for file_path in missing_files:
        ext = file_path.suffix.lower()
        
        if ext in image_exts: file_type = "image"
        elif ext in video_exts: file_type = "video"
        elif ext in audio_exts: file_type = "audio"
        else: file_type = "document"

        # 1. Safely extract the EXIF data that survived the compression move
        m = get_rich_metadata(file_path, file_type, ext)
        file_size_kb = round(os.path.getsize(file_path) / 1024, 2)
        
        # 2. Restore the Reverse Geocoding
        location_str = get_location_name(m["lat"], m["lon"])
        
        source = "misc" # Defaulting to misc since the staging folders are gone
        parsed_date = get_fallback_date(file_path, m["date_taken"])

        # 3. Insert full rich metadata into the DB
        cursor.execute("""
            INSERT INTO media 
            (original_name, current_path, file_type, source, date_taken, 
            file_size_kb, width, height, camera_model, f_stop, exposure_time, 
            iso, flash_fired, latitude, longitude, location_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_path.name, str(file_path), file_type, source, parsed_date.strftime("%Y-%m-%d %H:%M:%S"), 
            file_size_kb, m["width"], m["height"], m["camera_model"], m["f_stop"], 
            m["exposure_time"], m["iso"], m["flash_fired"], m["lat"], m["lon"], location_str
        ))
        
        media_id = cursor.lastrowid
        files_recovered += 1

        # 4. Recover the ML Face Vectors
        if file_type in ["image", "video"]:
            path_hash = hashlib.md5(str(file_path).encode('utf-8')).hexdigest()
            thumb_path = THUMB_DIR / f"{path_hash}.jpg"
            
            if not thumb_path.exists():
                thumb_path = generate_thumbnail(file_path, file_type)

            if thumb_path and thumb_path.exists():
                try:
                    with Image.open(thumb_path) as t_img:
                        thumb_w, thumb_h = t_img.size

                    import face_recognition
                    image = face_recognition.load_image_file(str(thumb_path))
                    face_locations = face_recognition.face_locations(image)
                    face_encodings = face_recognition.face_encodings(image, known_face_locations=face_locations)
                    
                    for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
                        cursor.execute("""
                            INSERT INTO faces (media_id, encoding, box_top, box_right, box_bottom, box_left, exclude_from_ml) 
                            VALUES (?, ?, ?, ?, ?, ?, 0)
                        """, (media_id, encoding.tobytes(), top, right, bottom, left))
                        faces_recovered += 1
                except Exception as e:
                    print(f"Failed to recover faces for {file_path.name}: {e}")

        conn.commit()
        print(f"Recovered: {file_path.name} | Location: {location_str}")

    conn.close()
    print(f"\nReconciliation Complete! Added {files_recovered} missing files and mapped {faces_recovered} faces.")

if __name__ == "__main__":
    reconcile_database()
