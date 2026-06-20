import os
import sqlite3
import subprocess
import hashlib
from pathlib import Path
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

# Register HEIC opener for Apple photos
register_heif_opener()

# Configuration
BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"
THUMB_DIR = BASE_DIR / ".thumbnails"

# Ensure the hidden cache directory exists
THUMB_DIR.mkdir(parents=True, exist_ok=True)

def generate_missing_thumbnails():
    if not DB_PATH.exists():
        print("Database not found. Please ensure your archive is initialized.")
        return

    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Fetch all files from the database
    cursor.execute("SELECT current_path, file_type, original_name FROM media")
    files = cursor.fetchall()
    conn.close()

    if not files:
        print("No files found in the database.")
        return

    print(f"Found {len(files)} total files in the archive. Scanning for missing thumbnails...")

    success_count = 0
    skip_count = 0
    error_count = 0

    for idx, (path_str, file_type, original_name) in enumerate(files, 1):
        file_path = Path(path_str)
        
        # Skip if the physical file is missing
        if not file_path.exists():
            print(f"[{idx}/{len(files)}] WARNING: Physical file missing -> {original_name}")
            error_count += 1
            continue

        # Skip documents
        if file_type not in ["image", "video"]:
            skip_count += 1
            continue

        # Generate the unique cache hash
        path_hash = hashlib.md5(str(file_path).encode('utf-8')).hexdigest()
        cache_path = THUMB_DIR / f"{path_hash}.jpg"

        # If it already exists, skip instantly
        if cache_path.exists():
            skip_count += 1
            continue

        # Process Image
        if file_type == "image":
            try:
                with Image.open(file_path) as img:
                    img = ImageOps.exif_transpose(img) 
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.thumbnail((400, 400))
                    img.save(cache_path, "JPEG", quality=75)
                print(f"[{idx}/{len(files)}] Generated Photo -> {original_name}")
                success_count += 1
            except Exception as e:
                print(f"[{idx}/{len(files)}] ERROR on {original_name}: {e}")
                error_count += 1

        # Process Video
        elif file_type == "video":
            try:
                cmd = [
                    "ffmpeg", "-y", "-i", str(file_path), 
                    "-ss", "00:00:00.100", "-vframes", "1", 
                    "-vf", "scale=400:-1", str(cache_path)
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                print(f"[{idx}/{len(files)}] Generated Video -> {original_name}")
                success_count += 1
            except Exception as e:
                print(f"[{idx}/{len(files)}] ERROR on {original_name}: FFmpeg failed.")
                error_count += 1

    print("-" * 50)
    print("Thumbnail Backfill Complete!")
    print(f"Successfully generated: {success_count}")
    print(f"Skipped (Already existed or non-media): {skip_count}")
    print(f"Failed: {error_count}")

if __name__ == "__main__":
    generate_missing_thumbnails()
