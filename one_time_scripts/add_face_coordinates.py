import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "everything/personal/backup/media_index.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE faces ADD COLUMN box_top INTEGER")
    cursor.execute("ALTER TABLE faces ADD COLUMN box_right INTEGER")
    cursor.execute("ALTER TABLE faces ADD COLUMN box_bottom INTEGER")
    cursor.execute("ALTER TABLE faces ADD COLUMN box_left INTEGER")
    conn.commit()
    print("Bounding box columns added successfully!")
except sqlite3.OperationalError:
    print("Columns already exist.")
finally:
    conn.close()
