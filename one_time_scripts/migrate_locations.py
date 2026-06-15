import sqlite3
from pathlib import Path
import reverse_geocoder as rg

DB_PATH = Path.home() / "everything/personal/backup/media_index.db"

def upgrade_database():
    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Safely add the new column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE media ADD COLUMN location_name TEXT")
        print("Added 'location_name' column to schema.")
    except sqlite3.OperationalError:
        print("'location_name' column already exists. Proceeding to geocode...")

    # 2. Create the index for fast searching
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_location ON media(location_name)")
    
    # 3. Fetch all rows that have GPS data but no location name yet
    cursor.execute("""
        SELECT id, latitude, longitude 
        FROM media 
        WHERE latitude IS NOT NULL 
          AND longitude IS NOT NULL 
          AND location_name IS NULL
    """)
    rows_to_update = cursor.fetchall()

    if not rows_to_update:
        print("No files require geocoding. Database is fully up to date.")
        conn.close()
        return

    print(f"Found {len(rows_to_update)} files to geocode. Processing...")

    # 4. Batch process the coordinates
    update_count = 0
    for row in rows_to_update:
        media_id, lat, lon = row
        try:
            geo_result = rg.search((lat, lon))
            if geo_result:
                city = geo_result[0].get('name', '')
                state = geo_result[0].get('admin1', '')
                location_str = f"{city}, {state}".strip(", ")

                cursor.execute(
                    "UPDATE media SET location_name = ? WHERE id = ?", 
                    (location_str, media_id)
                )
                update_count += 1
        except Exception as e:
            print(f"Failed to geocode ID {media_id}: {e}")

    # 5. Commit all changes at once
    conn.commit()
    conn.close()
    print(f"Migration complete! Successfully added locations to {update_count} files.")

if __name__ == "__main__":
    upgrade_database()
