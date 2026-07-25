# Local Media Archiver & Search Engine

A lightweight, privacy-focused pipeline built for Linux to locally organize, compress, index, and instantly search bulk smartphone media backups. 

Instead of relying on cloud services, this tool uses a local SQLite database to index deep EXIF and video metadata, allowing for instantaneous queries via a Command Line Interface (CLI) or a lightweight local web UI. It features aggressive offline compression, strict chronological sorting, offline reverse geocoding, and **on-device hybrid facial recognition** to keep local storage footprints small while maintaining a highly searchable archive.

The intention behind this project is for me to be able to regularly take backups of my smartphone media into a staging folder divided into 3 folders: "me" for taking backup out of my phone's DCIM/Camera folder, "shared" for backup of any media folders that get shared with me by friends/family after an event or trip, and "misc" for media backed up from anywhere else (WhatsApp media, documents, audio, etc.). This tool then organizes the media from the staging folder into monthly folders and builds a SQLite DB table with all the metadata extracted from the files, helping keep an archival of the media. 

*Note: The tool heavily compresses the files to enable keeping more files on a local system. But I am able to do this because I also have uncompressed backups on external drives. I would recommend you use the tool on redundant copies of your backup, not on the only copies.*

---

## 📂 Project Structure

    media_db/
    ├── organize.py               # Core engine: Multi-core extraction, compression, hashing, and indexing
    ├── search.py                 # Fast CLI tool for querying the SQLite database
    ├── viewer.py                 # Flask web app with main archive and precise People/Facial tagging UI
    ├── recluster.py              # Hybrid ML script (Average + Nearest Neighbor) to intelligently group faces
    ├── restore_backup.py         # Database rollback tool to undo clustering mistakes
    ├── one_time_scripts/
    │   ├── migrate_locations.py  # Schema updater to retroactively add offline geocoding
    │   ├── backfill_thumbs.py    # Generates missing lightweight thumbnails for older media
    │   └── backfill_faces.py     # Extracts and clusters faces for pre-existing media
    └── README.md

*Note: The script expects a physical directory structure at `~/everything/personal/backup/` containing `staging/me`, `staging/shared`, `staging/misc`, an `organized/` folder, and a hidden `.thumbnails/` cache.*

---

## ✨ Core Features

* **Multi-Core Processing Pipeline:** Spins up concurrent background workers to chew through massive media dumps simultaneously, utilizing your CPU heavily to drastically reduce processing time.
* **Bulletproof SHA-256 Deduplication:** Calculates a unique cryptographic signature for every single file. Instantly skips exact duplicates (even if they were renamed or moved), allowing you to safely dump entire phone backups into the staging folder incrementally.
* **Smart Hybrid Facial Clustering:** Extracts 128-dimensional facial vectors using `dlib`. Uses a robust hybrid algorithm—combining massive "Average Profiles" with strict "Nearest Neighbor" matching at a hard `0.42` distance threshold—to automatically cluster massive galleries of faces while strictly respecting your manual corrections.
* **Automated Safety Backups:** Automatically clones the `media_index.db` right before running facial clustering, giving you a one-click rollback mechanism if a machine-learning grouping goes awry.
* **Deep Metadata Extraction & Sync:** Reads EXIF data from images and parses hidden moov boxes from videos. Automatically handles iOS Live Photos by syncing GPS and timestamps from the master `.heic` to the orphaned `.mov` file.
* **RAW Sensor Support:** Uses `rawpy` to demosaic and convert uncompressed DSLR/Pro-mode camera files (`.dng`, `.cr2`, etc.) into optimized JPEGs.
* **Active Transcoding & Compression:** Converts heavy smartphone photos to optimized JPEGs and re-encodes bulky videos to H.265 (HEVC) using local CPU power.
* **Offline Reverse Geocoding:** Translates raw GPS coordinates into human-readable city and state names without pinging external internet APIs.
* **Blistering Fast UI:** The Flask frontend uses a dedicated `.thumbnails` cache, API-driven autocomplete dropdowns, and database-level pagination to ensure the browser never crashes, even when navigating an archive of 100,000+ files.

---

## 🛠 Prerequisites & Installation

This project is optimized for Linux (Ubuntu/Mint) and relies heavily on FFmpeg for video processing and a C++ compiler for the machine learning models.

**1. Install System Dependencies**

    sudo apt update
    sudo apt install ffmpeg cmake

**2. Install Python Libraries**

    pip install Pillow pillow-heif Flask reverse_geocoder rawpy exifread face_recognition scikit-learn numpy dlib

---

## 🚀 Usage Guide

### 1. Organizing New Media (`organize.py`)

Drop your files (or nested folders of files) into your staging directories (`me`, `shared`, or `misc`). Run the organizer to compress, geocode, sort, thumbnail, scan faces, and index everything. You can safely dump redundant backups here; the SHA-256 check will automatically ignore anything already in the database.

    python3 organize.py

*Note: Video compression is CPU-intensive. Bulk processing 4K videos will utilize all available cores and take time.*

### 2. Grouping & Correcting Faces (`recluster.py` & `restore_backup.py`)

While `organize.py` clusters automatically, you can run the standalone clustering script after making manual tag corrections in the UI to let the system learn from your inputs. 

    python3 recluster.py

If the clustering logic mistakenly merges two different people, you can instantly revert the database to its pre-clustered state:

    python3 restore_backup.py

### 3. The Visual Frontend (`viewer.py`)

Launch the lightweight Flask server to view a searchable, interactive gallery of your media directly in your web browser.

    python3 viewer.py

Open `http://127.0.0.1:5000` in Firefox or Chrome to access the gallery.

* **Media Archive:** Search by multi-person tags, location, camera model, or filename using instant API autocomplete. Sort dynamically by Date, Size, or Name.
* **People & Faces:** Switch to the `/people` tab to view unnamed clusters, assign names, and view dedicated galleries for specific people. Any manual tags you assign here act as "anchors" for future clustering.

### 4. Searching via CLI (`search.py`)

Perform instantaneous indexed searches across your archive directly from the terminal.

    python3 search.py --camera S23 --source shared
    python3 search.py --name IMG --flash
    python3 search.py --date 2026-05 --gps

---

## ⚙️ Advanced Configuration & One-Time Scripts

If you are upgrading an older version of your archive to support new features, **do not re-process your media**. Use the dedicated backfill scripts found in `one_time_scripts/` to safely update your SQLite schema and generate new data:

* **`migrate_locations.py`**: Adds GPS reverse-geocoding to older records.
* **`backfill_thumbs.py`**: Generates 400px JPEG thumbnails/video frames for faster UI loads.
* **`backfill_faces.py`**: A resumable script that scans all existing thumbnails for faces and runs the DBSCAN clustering algorithm.

### Pro-Tip: Shell Aliases

To make the tools accessible globally from your Linux terminal without typing the full path, add these to your `~/.bashrc`:

    alias media-sync="python3 /path/to/media_db/organize.py"
    alias media-find="python3 /path/to/media_db/search.py"
    alias media-view="python3 /path/to/media_db/viewer.py"
    alias media-cluster="python3 /path/to/media_db/recluster.py"
    alias media-undo="python3 /path/to/media_db/restore_backup.py"
