import sqlite3
import hashlib
import face_recognition
import numpy as np
from sklearn.cluster import DBSCAN
from pathlib import Path
import os
import subprocess
from PIL import Image, ImageOps

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
            FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX idx_media_id ON faces(media_id)")
    cursor.execute("CREATE INDEX idx_person_name ON faces(person_name)")
    cursor.execute("CREATE INDEX idx_cluster_id ON faces(cluster_id)")
    conn.commit()

    print("\n--- Starting Fresh High-Res Extraction ---")
    # Added file_type to the query so we know how to extract the 1200px frame
    cursor.execute("SELECT id, current_path, file_type FROM media WHERE file_type IN ('image', 'video')")
    media_items = cursor.fetchall()

    faces_found = 0
    for idx, (media_id, current_path, file_type) in enumerate(media_items, 1):
        path_hash = hashlib.md5(current_path.encode('utf-8')).hexdigest()
        thumb_path = THUMB_DIR / f"{path_hash}.jpg"

        if not thumb_path.exists(): continue

        try:
            # 1. Get the target thumbnail dimensions for the UI
            with Image.open(thumb_path) as t_img:
                thumb_w, thumb_h = t_img.size

            img_array = None
            ml_w, ml_h = 0, 0

            # 2. Generate the 1200px Intermediate Analysis Canvas
            if file_type == "image":
                with Image.open(current_path) as img:
                    img = ImageOps.exif_transpose(img)
                    if img.mode != 'RGB': img = img.convert('RGB')
                    
                    orig_w, orig_h = img.size
                    scale = min(1200 / orig_w, 1200 / orig_h)
                    if scale > 1: scale = 1 
                    
                    ml_img = img.resize((int(orig_w * scale), int(orig_h * scale)), Image.Resampling.LANCZOS)
                    ml_w, ml_h = ml_img.size
                    img_array = np.array(ml_img)
                    
            elif file_type == "video":
                temp_frame = BASE_DIR / f"temp_ml_frame_{media_id}.jpg"
                subprocess.run([
                    "ffmpeg", "-y", "-i", current_path,
                    "-ss", "00:00:00.100", "-vframes", "1",
                    "-vf", "scale='min(1200,iw)':-1", str(temp_frame)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                
                if temp_frame.exists():
                    with Image.open(temp_frame) as img:
                        ml_w, ml_h = img.size
                        img_array = np.array(img)
                    os.remove(temp_frame)

            # 3. Extract faces from the high-res canvas and translate coordinates back down
            if img_array is not None:
                face_locations = face_recognition.face_locations(img_array)
                face_encodings = face_recognition.face_encodings(img_array, known_face_locations=face_locations)
                
                if ml_w > 0:
                    ratio = thumb_w / ml_w
                    for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
                        t_top = int(top * ratio)
                        t_right = int(right * ratio)
                        t_bottom = int(bottom * ratio)
                        t_left = int(left * ratio)
                        
                        cursor.execute("""
                            INSERT INTO faces (media_id, encoding, box_top, box_right, box_bottom, box_left, exclude_from_ml) 
                            VALUES (?, ?, ?, ?, ?, ?, 0)
                        """, (media_id, encoding.tobytes(), t_top, t_right, t_bottom, t_left))
                        faces_found += 1
                        
            if idx % 100 == 0:
                print(f"Scanned {idx}/{len(media_items)}... found {faces_found} faces.")
                conn.commit()
        except Exception as e: 
            print(f"Error processing ID {media_id}: {e}")

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
