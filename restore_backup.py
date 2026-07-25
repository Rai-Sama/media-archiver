from pathlib import Path
import shutil
import sys

BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"
BACKUP_PATH = BASE_DIR / "media_index_backup.db"

def restore_database():
    print("--- ⏪ INITIATING DATABASE RESTORE ---")
    
    if not BACKUP_PATH.exists():
        print("❌ Error: No backup file found. Cannot restore.")
        sys.exit(1)
        
    print(f"Found backup file: {BACKUP_PATH.name}")
    print("Overwriting current database with backup...")
    
    try:
        shutil.copy2(BACKUP_PATH, DB_PATH)
        print("\n✅ Restore successful! Your tags are exactly as they were before the last run.")
        print("Refresh your web UI.")
    except Exception as e:
        print(f"\n❌ Restore failed: {e}")

if __name__ == "__main__":
    restore_database()
