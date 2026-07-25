import sqlite3
import numpy as np
from sklearn.cluster import DBSCAN
from pathlib import Path
import shutil

BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"
BACKUP_PATH = BASE_DIR / "media_index_backup.db"

def hybrid_recluster():
    print("--- 🧬 Running Hybrid Re-Clustering (Average + Nearest Neighbor) ---")
    
    # 0. CREATE A SAFETY BACKUP FIRST
    print(f"Creating safety backup at: {BACKUP_PATH.name}...")
    try:
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print("✅ Backup created successfully.")
    except Exception as e:
        print(f"❌ Backup failed! Aborting script to be safe: {e}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Nuke bad auto-tags so the system can re-evaluate your corrections
    cursor.execute("UPDATE faces SET person_name = NULL, cluster_id = NULL WHERE cluster_id = -1")
    
    # 2. Clear old junk untagged clusters
    cursor.execute("UPDATE faces SET cluster_id = NULL WHERE person_name IS NULL")
    conn.commit()

    # 3. Gather Known Anchors (Manual Tags Only)
    cursor.execute("SELECT person_name, encoding FROM faces WHERE person_name IS NOT NULL AND exclude_from_ml = 0 AND encoding IS NOT NULL")
    known_rows = cursor.fetchall()

    anchors = {}
    for name, blob in known_rows:
        try:
            enc = np.frombuffer(blob, dtype=np.float64)
            if name not in anchors:
                anchors[name] = []
            anchors[name].append(enc)
        except Exception: 
            pass

    # Calculate the Average Profiles for the bulk restoration
    anchor_profiles = {}
    for name, encs in anchors.items():
        anchor_profiles[name] = np.mean(encs, axis=0)

    # 4. Fetch Unknown Faces
    cursor.execute("SELECT id, encoding FROM faces WHERE person_name IS NULL AND exclude_from_ml = 0 AND encoding IS NOT NULL")
    unknown_rows = cursor.fetchall()

    if not unknown_rows:
        print("No unknown faces to cluster.")
        conn.close()
        return

    unknown_ids = []
    unknown_encs = []
    for row_id, blob in unknown_rows:
        try:
            unknown_ids.append(row_id)
            unknown_encs.append(np.frombuffer(blob, dtype=np.float64))
        except Exception: 
            pass

    # 5. Hybrid Matching: Best of Both Worlds
    print(f"Matching unknown faces using Hybrid Logic...")
    leftover_ids = []
    leftover_encs = []
    matches_found = 0

    for f_id, enc in zip(unknown_ids, unknown_encs):
        best_match_name = None
        best_distance = 0.42 # Locked strictly at 0.42 to keep junk out

        for name, enc_list in anchors.items():
            # Check 1: Distance to the massive Average Profile (Restores the big galleries)
            avg_dist = np.linalg.norm(anchor_profiles[name] - enc)
            
            # Check 2: Distance to the Nearest Individual Manual Tag (Gives corrections 100% power)
            distances = np.linalg.norm(enc_list - enc, axis=1)
            nn_dist = np.min(distances)
            
            # The face gets whichever distance is closer!
            min_dist = min(avg_dist, nn_dist)
            
            if min_dist < best_distance:
                best_distance = min_dist
                best_match_name = name

        if best_match_name:
            cursor.execute("UPDATE faces SET person_name = ?, cluster_id = -1 WHERE id = ?", (best_match_name, f_id))
            matches_found += 1
        else:
            leftover_ids.append(f_id)
            leftover_encs.append(enc)

    print(f"Auto-tagged {matches_found} faces. Galleries restored and corrections applied.")

    # 6. Run DBSCAN on the leftovers
    if leftover_encs:
        print(f"Running DBSCAN on the remaining unknown faces...")
        clt = DBSCAN(metric="euclidean", n_jobs=-1, eps=0.38, min_samples=4)
        clt.fit(leftover_encs)

        cluster_ids = clt.labels_
        unique_clusters = len(set(cluster_ids)) - (1 if -1 in cluster_ids else 0)
        print(f"Grouped remaining faces into {unique_clusters} inbox clusters.")

        updates = [(int(cid), fid) for fid, cid in zip(leftover_ids, cluster_ids)]
        cursor.executemany("UPDATE faces SET cluster_id = ? WHERE id = ?", updates)

    conn.commit()
    conn.close()
    print("Re-clustering complete! Check your Viewer UI.")

if __name__ == "__main__":
    hybrid_recluster()
