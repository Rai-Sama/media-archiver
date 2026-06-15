import sqlite3
import subprocess
import json
import re
from pathlib import Path
import reverse_geocoder as rg

DB_PATH = Path.home() / "everything/personal/backup/media_index.db"

def sync_video_database():
    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Grab all videos currently in the database
    cursor.execute("SELECT id, current_path, original_name FROM media WHERE file_type = 'video'")
    videos = cursor.fetchall()
    
    if not videos:
        print("No videos found in the database to sync.")
        return

    print(f"Found {len(videos)} videos. Scanning for injected metadata...")
    update_count = 0

    for vid_id, path_str, original_name in videos:
        vid_path = Path(path_str)
        if not vid_path.exists():
            continue
            
        try:
            # Use ffprobe to read the newly injected tags
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(vid_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)
            
            tags = data.get("format", {}).get("tags", {})
            # Normalize tag keys to lowercase
            tags = {k.lower(): v for k, v in tags.items()}
            
            # Extract Date
            date_taken = None
            raw_date = tags.get("creation_time")
            if raw_date:
                date_taken = raw_date.replace("T", " ")[:19]
                
            # Extract Camera Model
            camera = tags.get("model") or tags.get("com.android.model") or tags.get("com.apple.quicktime.model")
            
            # Extract GPS and Geocode
            lat, lon, loc_name = None, None, None
            loc_str = tags.get("location") or tags.get("location-eng")
            
            if loc_str:
                # Parse ISO 6709 format (e.g., +25.5941+085.1376/)
                match = re.search(r'([+-]\d+\.\d+)([+-]\d+\.\d+)', loc_str)
                if match:
                    lat = float(match.group(1))
                    lon = float(match.group(2))
                    
                    # Reverse geocode instantly
                    geo_result = rg.search((lat, lon))
                    if geo_result:
                        city = geo_result[0].get('name', '')
                        state = geo_result[0].get('admin1', '')
                        loc_name = f"{city}, {state}".strip(", ")
            
            # Only update the database if we actually found new metadata
            if camera or loc_name or date_taken:
                cursor.execute("""
                    UPDATE media 
                    SET date_taken = COALESCE(?, date_taken), 
                        camera_model = COALESCE(?, camera_model), 
                        latitude = COALESCE(?, latitude), 
                        longitude = COALESCE(?, longitude), 
                        location_name = COALESCE(?, location_name)
                    WHERE id = ?
                """, (date_taken, camera, lat, lon, loc_name, vid_id))
                
                update_count += 1
                print(f"Synced -> {original_name} | {camera or 'Unknown Device'} | {loc_name or 'No GPS'}")
                
        except Exception as e:
            print(f"Error processing {original_name}: {e}")
            pass
            
    conn.commit()
    conn.close()
    
    print("-" * 50)
    print(f"Database Sync Complete! Successfully updated {update_count} videos.")

if __name__ == "__main__":
    sync_video_database()
