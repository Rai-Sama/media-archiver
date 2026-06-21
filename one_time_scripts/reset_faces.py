import sqlite3
import hashlib
import face_recognition
import numpy as np
from sklearn.cluster import DBSCAN
from pathlib import Path

BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"
THUMB_DIR = BASE_DIR / ".thumbnails"

def clean_slate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Nuking the old faces table...")
    cursor.execute("DROP TABLE IF EXISTS faces")
    
    print("Recreating table with Bounding Box tracking...")
    cursor.execute("""
        CREATE TABLE faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER,
            encoding BLOB,
            cluster_id INTEGER,
            person_name TEXT,
            exclude_from_ml INTEGER DEFAULT 0,
            box_top INTEGER,
            box_right INTEGER,
            box_bottom INTEGER,
            box_left INTEGER,
            FOREIGN KEY(media_id) REFERENCES media(id)
        )
    """)
    cursor.execute("CREATE INDEX idx_media_id ON faces(media_id)")
    cursor.execute("CREATE INDEX idx_person_name ON faces(person_name)")
    cursor.execute("CREATE INDEX idx_cluster_id ON faces(cluster_id)")
    conn.commit()

    print("\n--- Starting Fresh Extraction ---")
    cursor.execute("SELECT id, current_path FROM media WHERE file_type IN ('image', 'video')")
    media_items = cursor.fetchall()

    faces_found = 0
    for idx, (media_id, current_path) in enumerate(media_items, 1):
        path_hash = hashlib.md5(current_path.encode('utf-8')).hexdigest()
        thumbnail_path = THUMB_DIR / f"{path_hash}.jpg"

        if not thumbnail_path.exists(): continue

        try:
            image = face_recognition.load_image_file(str(thumbnail_path))
            face_locations = face_recognition.face_locations(image)
            face_encodings = face_recognition.face_encodings(image, known_face_locations=face_locations)
            
            for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
                cursor.execute("""
                    INSERT INTO faces (media_id, encoding, box_top, box_right, box_bottom, box_left) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (media_id, encoding.tobytes(), top, right, bottom, left))
                faces_found += 1
                
            if idx % 100 == 0:
                print(f"Scanned {idx}/{len(media_items)}... found {faces_found} faces.")
                conn.commit()
        except Exception: pass

    conn.commit()
    print(f"Extraction Complete. Extracted {faces_found} faces with perfect coordinates.")

    print("\n--- Running DBSCAN Clustering ---")
    cursor.execute("SELECT id, encoding FROM faces WHERE exclude_from_ml = 0 AND encoding IS NOT NULL")
    rows = cursor.fetchall()

    face_ids = []
    encodings = []
    for row_id, blob in rows:
        face_ids.append(row_id)
        encodings.append(np.frombuffer(blob, dtype=np.float64))

    if encodings:
        clt = DBSCAN(metric="euclidean", n_jobs=-1, eps=0.45, min_samples=3)
        clt.fit(encodings)
        updates = [(int(cid), fid) for fid, cid in zip(face_ids, clt.labels_)]
        cursor.executemany("UPDATE faces SET cluster_id = ? WHERE id = ?", updates)
        unique_clusters = len(set(clt.labels_)) - (1 if -1 in clt.labels_ else 0)
        print(f"Grouped into {unique_clusters} distinct people.")

    conn.commit()
    conn.close()
    print("Clean Slate complete! Ready for UI tagging.")

if __name__ == "__main__":
    clean_slate()
