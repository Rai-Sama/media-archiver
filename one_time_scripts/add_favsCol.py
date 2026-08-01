import sqlite3
from pathlib import Path

BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"

def upgrade_schema():
    print("--- 🌟 Upgrading Schema: Favorites Feature ---")
    
    if not DB_PATH.exists():
        print(f"❌ Error: Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Add the is_favorite column
        try:
            cursor.execute("ALTER TABLE media ADD COLUMN is_favorite INTEGER DEFAULT 0")
            print("✅ Added 'is_favorite' column to media table.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️ Column 'is_favorite' already exists. Skipping.")
            else:
                raise e

        # 2. Add an index for fast filtering in the UI
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_favorite ON media(is_favorite)")
        print("✅ Verified database index for fast favorite queries.")
        
        conn.commit()
        print("🎉 Schema upgrade complete!")
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    upgrade_schema()
