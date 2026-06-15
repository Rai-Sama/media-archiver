import os
import sqlite3
import subprocess
from pathlib import Path

# Configuration
BASE_DIR = Path.home() / "everything/personal/backup"
RECOVERY_DIR = BASE_DIR / "recovery_videos"
DB_PATH = BASE_DIR / "media_index.db"

def inject_video_metadata():
    if not RECOVERY_DIR.exists():
        print(f"Please create the directory {RECOVERY_DIR} and place your original videos there.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    video_exts = {'.mp4', '.mkv', '.mov', '.avi'}
    success_count = 0
    fail_count = 0
    skipped_photos = 0

    print("Scanning recovery directory for original videos...")
    
    for original_path in RECOVERY_DIR.rglob("*"):
        if original_path.is_dir():
            continue
            
        # SAFETY CHECK: Ignore photos and documents completely
        if original_path.suffix.lower() not in video_exts:
            skipped_photos += 1
            continue
            
        # 1. Find where the compressed version lives right now
        cursor.execute("SELECT current_path FROM media WHERE original_name = ?", (original_path.name,))
        result = cursor.fetchone()
        
        if not result:
            print(f"Skipping {original_path.name}: Could not find a match in the database.")
            fail_count += 1
            continue
            
        compressed_path = Path(result[0])
        
        if not compressed_path.exists():
            print(f"Skipping {original_path.name}: The compressed file is missing from the disk.")
            fail_count += 1
            continue

        temp_output = compressed_path.with_suffix('.temp.mp4')
        print(f"Injecting metadata into: {compressed_path.name}...")
        
        # 2. The FFmpeg Magic Command
        cmd = [
            "ffmpeg", "-y", 
            "-i", str(original_path), 
            "-i", str(compressed_path), 
            "-map", "1", 
            "-map_metadata", "0", 
            "-movflags", "use_metadata_tags",
            "-c", "copy", 
            "-v", "quiet", 
            str(temp_output)
        ]
        
        try:
            subprocess.run(cmd, check=True)
            
            # 3. Replace the stripped file with the newly injected file
            os.replace(temp_output, compressed_path)
            success_count += 1
            
        except subprocess.CalledProcessError:
            print(f"ERROR: Failed to inject metadata for {original_path.name}")
            if temp_output.exists():
                os.remove(temp_output)
            fail_count += 1

    conn.close()
    
    print("-" * 50)
    print("Injection Complete!")
    print(f"Successfully updated: {success_count} videos.")
    print(f"Ignored: {skipped_photos} non-video files.")
    print(f"Failed or missing: {fail_count} videos.")
    print("You can now safely delete the original files from the recovery_videos folder.")

if __name__ == "__main__":
    inject_video_metadata()
