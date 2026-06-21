import sqlite3
import hashlib
import face_recognition
import numpy as np
from sklearn.cluster import DBSCAN
from pathlib import Path
import os
import subprocess
from PIL import Image, ImageOps
import concurrent.futures
import tempfile

BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"
THUMB_DIR = BASE_DIR / ".thumbnails"

def clean_slate_tables():
    """Nukes and prepares the database schema on the main thread."""
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
    conn.close()

def extract_faces_from_item_worker(args):
    """
    Isolated worker function. Processes a single media item, scales it to the
    1200px intermediate canvas, computes encodings, and returns translated coordinates.
    """
    media_id, current_path, file_type, thumb_path_str = args
    thumb_path = Path(thumb_path_str)
    extracted_faces = []

    if not thumb_path.exists():
        return media_id, extracted_faces

    try:
        # 1. Get UI thumbnail target geometry
        with Image.open(thumb_path) as t_img:
            thumb_w, thumb_h = t_img.size

        img_array = None
        ml_w, ml_h = 0, 0
        temp_path = None

        # 2. Build the 1200px Intermediate Analysis Canvas
        if file_type == "image":
            with Image.open(current_path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != 'RGB': 
                    img = img.convert('RGB')
                
                orig_w, orig_h = img.size
                scale = min(1200 / orig_w, 1200 / orig_h)
                if scale > 1: 
                    scale = 1 
                
                ml_img = img.resize((int(orig_w * scale), int(orig_h * scale)), Image.Resampling.LANCZOS)
                ml_w, ml_h = ml_img.size
                img_array = np.array(ml_img)
                
        elif file_type == "video":
            # Guarded temporary file allocation
            with tempfile.NamedTemporaryFile(suffix=".jpg", dir=BASE_DIR, delete=False) as tf:
                temp_path = tf.name
                
            try:
                # pass '-threads 1' to keep system responsive
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(current_path),
                    "-ss", "00:00:00.100", "-vframes", "1",
                    "-vf", "scale='min(1200,iw)':-1", "-threads", "1", temp_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                
                if Path(temp_path).exists():
                    with Image.open(temp_path) as img:
                        ml_w, ml_h = img.size
                        img_array = np.array(img)
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)

        # 3. Compute Dlib vectors and mathematically step-down coordinates
        if img_array is not None:
            face_locations = face_recognition.face_locations(img_array)
            face_encodings = face_recognition.face_encodings(img_array, known_face_locations=face_locations)
            
            if ml_w > 0:
                ratio = thumb_w / ml_w
                for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
                    extracted_faces.append({
                        "encoding": encoding.tobytes(),
                        "box_top": int(top * ratio),
                        "box_right": int(right * ratio),
                        "box_bottom": int(bottom * ratio),
                        "box_left": int(left * ratio)
                    })
                    
    except Exception as e:
        print(f"Error processing media ID {media_id}: {e}")
        
    return media_id, extracted_faces

def process_batch_extraction():
    print("\n--- Starting Fresh High-Res Parallel Extraction ---")
    
    clean_slate_tables()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, current_path, file_type FROM media WHERE file_type IN ('image', 'video')")
    media_items = cursor.fetchall()
    
    tasks = []
    for media_id, current_path, file_type in media_items:
        path_hash = hashlib.md5(current_path.encode('utf-8')).hexdigest()
        thumb_path_str = str(THUMB_DIR / f"{path_hash}.jpg")
        tasks.append((media_id, current_path, file_type, thumb_path_str))
        
    total_tasks = len(tasks)
    print(f"Queued {total_tasks} existing files for processing.")
    
    if total_tasks == 0:
        conn.close()
        return

    # Slicing the workload into memory-safe chunks
    CHUNK_SIZE = 500
    task_chunks = [tasks[i:i + CHUNK_SIZE] for i in range(0, total_tasks, CHUNK_SIZE)]
    
    max_w = min(4, os.cpu_count() or 1)
    print(f"Processing via {max_w} workers...")
    
    faces_found = 0
    files_processed = 0
    
    for chunk in task_chunks:
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_w) as executor:
            future_to_item = {executor.submit(extract_faces_from_item_worker, task): task for task in chunk}
            
            for future in concurrent.futures.as_completed(future_to_item):
                media_id, faces = future.result()
                
                # Single-threaded serial persistence layer to guarantee SQLite thread safety
                for face in faces:
                    cursor.execute("""
                        INSERT INTO faces (media_id, encoding, box_top, box_right, box_bottom, box_left, exclude_from_ml) 
                        VALUES (?, ?, ?, ?, ?, ?, 0)
                    """, (media_id, face["encoding"], face["box_top"], face["box_right"], 
                          face["box_bottom"], face["box_left"]))
                    faces_found += 1
                
                files_processed += 1
                if files_processed % 100 == 0:
                    print(f"Scanned {files_processed}/{total_tasks}... Found {faces_found} faces.")
                    conn.commit()
                    
        conn.commit()  # Flush chunk results directly to disk

    print(f"Extraction Complete. Total faces captured: {faces_found}")
    conn.close()

def cluster_faces():
    print("\n--- Running DBSCAN Clustering ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, encoding FROM faces WHERE exclude_from_ml = 0 AND encoding IS NOT NULL")
    rows = cursor.fetchall()

    face_ids = []
    encodings = []
    for row_id, blob in rows:
        face_ids.append(row_id)
        encodings.append(np.frombuffer(blob, dtype=np.float64))

    if encodings:
        print(f"Clustering {len(encodings)} face vectors using all available threads...")
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
    process_batch_extraction()
    cluster_faces()
