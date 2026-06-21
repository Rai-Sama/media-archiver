import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "everything/personal/backup/media_index.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # Add the boolean column (0 = ML generated, 1 = Manually Tagged)
    cursor.execute("ALTER TABLE faces ADD COLUMN is_manual INTEGER DEFAULT 0")
    
    # If you already ran the previous script to create manual_tags, we can drop it to keep things clean
    cursor.execute("DROP TABLE IF EXISTS manual_tags")
    
    conn.commit()
    print("Successfully merged into a single-table architecture!")
except sqlite3.OperationalError:
    print("Column already exists or database is locked.")
finally:
    conn.close()
