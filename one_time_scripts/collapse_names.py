import sqlite3
from pathlib import Path

BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"

def collapse_name_cases():
    print("--- 🔠 Standardizing Face Tags to Lowercase ---")
    
    if not DB_PATH.exists():
        print(f"❌ Error: Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # This will update all existing person_name entries to their lowercase equivalents
        cursor.execute("UPDATE faces SET person_name = LOWER(person_name) WHERE person_name IS NOT NULL")
        
        updated_rows = cursor.rowcount
        conn.commit()
        
        print(f"✅ Successfully standardized {updated_rows} face tags to lowercase.")
        print("🎉 The 'People & Faces' gallery will now merge identical names regardless of capitalization!")
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    collapse_name_cases()
