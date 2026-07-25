import sqlite3
from pathlib import Path

BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"

def emergency_cleanup():
    print("--- 🚨 INITIATING EMERGENCY CLEANUP 🚨 ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. NUKE ALL AUTO-TAGS FROM THE BAD SCRIPT
    # Every mistake the script made was flagged with cluster_id = -1. This wipes them out.
    cursor.execute("UPDATE faces SET person_name = NULL, cluster_id = NULL WHERE cluster_id = -1")
    reverted_count = cursor.rowcount
    print(f"✅ Instantly wiped {reverted_count} bad auto-tags from the database.")

    # 2. OPTIONAL: NUKE A CORRUPTED PERSON ENTIRELY
    print("\nIf a specific person's gallery is still too corrupted with manual mistakes,")
    print("you can reset them entirely. They will go back into the 'Inbox / Unknown' pool.")
    bad_name = input("Type the exact name of the corrupted person (or press Enter to skip): ").strip()
    
    if bad_name:
        cursor.execute("UPDATE faces SET person_name = NULL, cluster_id = NULL WHERE person_name = ?", (bad_name,))
        wiped_count = cursor.rowcount
        print(f"✅ Reset {wiped_count} tags for '{bad_name}'.")
    else:
        print("Skipped manual tag reset.")

    conn.commit()
    conn.close()
    print("\nCleanup complete! Refresh your web UI.")

if __name__ == "__main__":
    emergency_cleanup()
