import sqlite3
import hashlib
import face_recognition
import numpy as np
from sklearn.cluster import DBSCAN
from pathlib import Path

# Configuration
BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"
THUMB_DIR = BASE_DIR / ".thumbnails"

def backfill_faces_and_cluster():
    if not DB_PATH.exists():
        print("Database not found. Please ensure your archive is initialized.")
        return

    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Fetch all images and videos from the archive
    cursor.execute("SELECT id, current_path FROM media WHERE file_type IN ('image', 'video')")
    media_items = cursor.fetchall()

    # 2. Find which media_ids already have faces so we can skip them
    # Note: Photos that genuinely have 0 faces will be rescanned, but scanning a 400px thumbnail takes milliseconds.
    cursor.execute("SELECT DISTINCT media_id FROM faces")
    already_scanned_ids = {row[0] for row in cursor.fetchall()}

    print(f"Found {len(media_items)} total media items.")
    
    new_faces_found = 0
    scanned_count = 0
    error_count = 0

    print("\n--- Phase 1: Facial Extraction ---")
    for media_id, current_path in media_items:
        # Skip if we already successfully found faces in this file previously
        if media_id in already_scanned_ids:
            continue

        # Reconstruct the thumbnail path
        path_hash = hashlib.md5(current_path.encode('utf-8')).hexdigest()
        thumbnail_path = THUMB_DIR / f"{path_hash}.jpg"

        if not thumbnail_path.exists():
            continue # If the thumbnail failed to generate previously, skip facial scanning

        try:
            # Load the tiny thumbnail into memory
            image = face_recognition.load_image_file(str(thumbnail_path))
            
            # Find all faces and convert them to math vectors
            face_encodings = face_recognition.face_encodings(image)
            
            for encoding in face_encodings:
                encoding_blob = encoding.tobytes()
                cursor.execute(
                    "INSERT INTO faces (media_id, encoding) VALUES (?, ?)", 
                    (media_id, encoding_blob)
                )
                new_faces_found += 1
                
            scanned_count += 1
            
            # Batch commit every 100 scans so progress is saved if you cancel the script
            if scanned_count % 100 == 0:
                print(f"Scanned {scanned_count} files... found {new_faces_found} faces so far.")
                conn.commit() 
                
        except Exception as e:
            error_count += 1

    # Final commit for the extraction phase
    conn.commit()
    print(f"Extraction Complete! Scanned {scanned_count} files, found {new_faces_found} faces. Errors: {error_count}")

    # --- Phase 2: DBSCAN Clustering ---
    print("\n--- Phase 2: Facial Clustering ---")
    cursor.execute("SELECT id, encoding FROM faces")
    rows = cursor.fetchall()

    if not rows:
        print("No faces found in the database to cluster.")
        conn.close()
        return

    face_ids = []
    encodings = []

    print("Loading faces into memory...")
    for row_id, blob in rows:
        try:
            encoding = np.frombuffer(blob, dtype=np.float64)
            face_ids.append(row_id)
            encodings.append(encoding)
        except Exception:
            pass

    if not encodings:
        print("No valid encodings found.")
        conn.close()
        return

    print(f"Running DBSCAN algorithm on {len(encodings)} faces...")
    # eps=0.45 is the strictness. min_samples=3 means someone must be in 3 photos to get a cluster.
    clt = DBSCAN(metric="euclidean", n_jobs=-1, eps=0.45, min_samples=3)
    clt.fit(encodings)

    cluster_ids = clt.labels_
    
    unique_clusters = len(set(cluster_ids)) - (1 if -1 in cluster_ids else 0)
    print(f"Success! Grouped faces into {unique_clusters} distinct people.")

    print("Saving cluster assignments to the database...")
    updates = [(int(cid), fid) for fid, cid in zip(face_ids, cluster_ids)]
    cursor.executemany("UPDATE faces SET cluster_id = ? WHERE id = ?", updates)
    
    conn.commit()
    conn.close()
    print("\nBackfill and Clustering Complete!")

if __name__ == "__main__":
    backfill_faces_and_cluster()
