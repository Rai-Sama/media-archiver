import sqlite3
from pathlib import Path

# Configuration
BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"

def add_filename_index():
    if not DB_PATH.exists():
        print("Database not found. Please ensure your archive is initialized.")
        return

    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Building B-Tree index for 'original_name'...")
    try:
        # Create the index
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON media(original_name)")
        conn.commit()
        print("✅ Index successfully built! Deduplication checks will now be instantaneous.")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_filename_index()
