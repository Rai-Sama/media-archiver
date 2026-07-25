import sqlite3
import numpy as np
from sklearn.cluster import DBSCAN
from pathlib import Path

BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"

def revert_and_recluster():
    print("--- 🔙 REVERTING TO ORIGINAL CLUSTERING LOGIC ---")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Nuke all the bad auto-tags from my recent scripts
    # This leaves your manual tags perfectly untouched.
    cursor.execute("UPDATE faces SET person_name = NULL, cluster_id = NULL WHERE cluster_id = -1")
    conn.commit()
    print("Wiped the recent bad auto-tags.")

    # 2. Clear out the old junk untagged clusters
    cursor.execute("UPDATE faces SET cluster_id = NULL WHERE person_name IS NULL")
    conn.commit()

    # 3. Gather Known Anchors
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

    # RESTORED: Create an average 128-d vector profile for each known person
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

    # 5. Match Unknowns to Average Profiles (Restored to original 0.42 threshold)
    print(f"Comparing unknown faces against {len(anchor_profiles)} known profiles...")
    leftover_ids = []
    leftover_encs = []
    matches_found = 0

    for f_id, enc in zip(unknown_ids, unknown_encs):
        best_match_name = None
        best_distance = 0.42 # RESTORED TO ORIGINAL

        for name, profile in anchor_profiles.items():
            dist = np.linalg.norm(profile - enc)
            if dist < best_distance:
                best_distance = dist
                best_match_name = name

        if best_match_name:
            cursor.execute("UPDATE faces SET person_name = ?, cluster_id = -1 WHERE id = ?", (best_match_name, f_id))
            matches_found += 1
        else:
            leftover_ids.append(f_id)
            leftover_encs.append(enc)

    print(f"Auto-tagged {matches_found} faces based on your original logic.")

    # 6. Run DBSCAN on the leftovers
    if leftover_encs:
        print(f"Running DBSCAN on the remaining unknown faces...")
        # RESTORED to your exact original parameters
        clt = DBSCAN(metric="euclidean", n_jobs=-1, eps=0.38, min_samples=4)
        clt.fit(leftover_encs)

        cluster_ids = clt.labels_
        unique_clusters = len(set(cluster_ids)) - (1 if -1 in cluster_ids else 0)
        print(f"Grouped remaining faces into {unique_clusters} inbox clusters.")

        updates = [(int(cid), fid) for fid, cid in zip(leftover_ids, cluster_ids)]
        cursor.executemany("UPDATE faces SET cluster_id = ? WHERE id = ?", updates)

    conn.commit()
    conn.close()
    print("Reverted completely! Refresh your Viewer UI.")

if __name__ == "__main__":
    revert_and_recluster()
