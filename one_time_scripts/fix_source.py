import sqlite3
from pathlib import Path

BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"

def fix_existing_sources():
    print("--- Retroactively Evicting Clutter from 'My Camera' ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Fix Snapchat
    cursor.execute("UPDATE media SET source = 'snapchat' WHERE source = 'me' AND original_name LIKE '%Snapchat%'")
    snap_count = cursor.rowcount

    # 2. Fix WhatsApp
    cursor.execute("UPDATE media SET source = 'whatsapp' WHERE source = 'me' AND (original_name LIKE '%WA0%' OR original_name LIKE '%WhatsApp%')")
    wa_count = cursor.rowcount

    # 3. Fix Screenshots & Screen Recordings
    cursor.execute("UPDATE media SET source = 'screenshots' WHERE source = 'me' AND (original_name LIKE '%Screenshot%' OR original_name LIKE '%Screen_Recording%')")
    screen_count = cursor.rowcount
    
    # 4. Fix Instagram
    cursor.execute("UPDATE media SET source = 'instagram' WHERE source = 'me' AND original_name LIKE '%Instagram%'")
    ig_count = cursor.rowcount

    conn.commit()
    conn.close()

    print(f"Fixed {snap_count} Snapchat files.")
    print(f"Fixed {wa_count} WhatsApp files.")
    print(f"Fixed {screen_count} Screenshots/Recordings.")
    print(f"Fixed {ig_count} Instagram files.")
    print("\nAll of these files have been successfully evicted from the 'My Camera' source category!")

if __name__ == "__main__":
    fix_existing_sources()
