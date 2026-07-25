import sqlite3
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"

def fix_greedy_dates():
    print("--- Fixing Impossible Dates & Re-Scanning Filenames ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, original_name, date_taken, current_path FROM media")
    rows = cursor.fetchall()

    fixes_applied = 0
    reverts_applied = 0

    # Pattern 1: Matches exactly 14 digits YYYYMMDD_HHMMSS (e.g., 20180522_153022)
    # The (?<!\d) and (?!\d) ensure we don't accidentally match inside a longer random ID
    # (20[0-2]\d) restricts the year from 2000 to 2029
    pattern_full = re.compile(r'(?<!\d)(20[0-2]\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[-_]?(\d{2})(\d{2})(\d{2})(?!\d)')
    
    # Pattern 2: Matches exactly 8 digits YYYYMMDD (e.g., IMG-20190522-WA0001, Snapchat-20170822)
    pattern_partial = re.compile(r'(?<!\d)(20[0-2]\d)(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)')

    for row_id, original_name, current_date, current_path in rows:
        match_full = pattern_full.search(original_name)
        match_partial = pattern_partial.search(original_name)
        
        new_date = None

        # Check for full datetime first
        if match_full:
            new_date = f"{match_full.group(1)}-{match_full.group(2)}-{match_full.group(3)} {match_full.group(4)}:{match_full.group(5)}:{match_full.group(6)}"
        # Fall back to date only (assume noon)
        elif match_partial:
            new_date = f"{match_partial.group(1)}-{match_partial.group(2)}-{match_partial.group(3)} 12:00:00"

        if new_date:
            if new_date != current_date:
                cursor.execute("UPDATE media SET date_taken = ? WHERE id = ?", (new_date, row_id))
                fixes_applied += 1
        else:
            # Revert any impossible dates (like 2095) caused by the previous script
            try:
                # Safely grab the first 4 characters to check the year
                year = int(str(current_date)[:4]) 
                
                if year > 2026 or year < 1990:
                    path_obj = Path(current_path)
                    if path_obj.exists():
                        # Read the physical file's modified time from the hard drive as a fallback
                        fallback = datetime.fromtimestamp(path_obj.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                        cursor.execute("UPDATE media SET date_taken = ? WHERE id = ?", (fallback, row_id))
                        reverts_applied += 1
            except (ValueError, TypeError):
                pass

    conn.commit()
    conn.close()
    
    print(f"Corrected {fixes_applied} dates using strict filename boundaries.")
    print(f"Reverted {reverts_applied} impossible dates back to their actual file modified time.")
    print("Refresh your browser UI!")

if __name__ == "__main__":
    fix_greedy_dates()
