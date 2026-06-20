import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "everything/personal/backup/media_index.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Create a dedicated table for faces
cursor.execute("""
    CREATE TABLE IF NOT EXISTS faces (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_id INTEGER,
        encoding BLOB,         -- The 128-d math vector
        cluster_id INTEGER,    -- Group number (e.g., 1, 2, 3)
        person_name TEXT,      -- The human name you assign in the UI
        FOREIGN KEY(media_id) REFERENCES media(id)
    )
""")

# Indexes for fast UI lookups
cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_id ON faces(media_id)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_person_name ON faces(person_name)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_cluster_id ON faces(cluster_id)")

conn.commit()
conn.close()
print("Facial Recognition tables added successfully!")
