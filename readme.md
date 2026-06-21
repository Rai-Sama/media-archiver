# Local Media Archiver & Search Engine

A lightweight, privacy-focused pipeline built for Linux to locally organize, compress, index, and instantly search bulk smartphone media backups. 

Instead of relying on cloud services, this tool uses a local SQLite database to index deep EXIF and video metadata, allowing for instantaneous queries via a Command Line Interface (CLI) or a lightweight local web UI. It features aggressive offline compression, strict chronological sorting, offline reverse geocoding, and **on-device facial recognition** to keep local storage footprints small while maintaining a highly searchable archive.

The intention behind this project is for me to be able to regularly take backups of my smartphone media into a staging folder divided into 3 folders: "me" for taking backup out of my phone's DCIM/Camera folder, "shared" for backup of any media folders that get shared with me by friends/family after an event or trip, and "misc" for media backed up from anywhere else (WhatsApp media, documents, audio, etc.). This tool then organizes the media from the staging folder into monthly folders and builds a SQLite DB table with all the metadata extracted from the files, helping keep an archival of the media. 

*Note: The tool heavily compresses the files to enable keeping more files on a local system. But I am able to do this because I also have uncompressed backups on external drives. I would recommend you use the tool on redundant copies of your backup, not on the only copies.*

---

## 📂 Project Structure

```text
media_db/
├── organize.py               # Core engine: Extracts, compresses, thumbnails, scans faces, and indexes
├── search.py                 # Fast CLI tool for querying the SQLite database
├── viewer.py                 # Flask web app with main archive and People/Facial tagging UI
├── cluster_faces.py          # Machine learning script (DBSCAN) to group unlabelled faces
├── one_time_scripts/
│   ├── migrate_locations.py  # Schema updater to retroactively add offline geocoding
│   ├── backfill_thumbs.py    # Generates missing lightweight thumbnails for older media
│   └── backfill_faces.py     # Extracts and clusters faces for pre-existing media
└── README.md

```

*Note: The script expects a physical directory structure at `~/everything/personal/backup/` containing `staging/me`, `staging/shared`, `staging/misc`, an `organized/` folder, and a hidden `.thumbnails/` cache.*

---

## ✨ Core Features

* **Deep Metadata Extraction & Sync:** Reads EXIF data from images and parses hidden moov boxes from videos. Automatically handles iOS Live Photos by syncing GPS and timestamps from the master `.heic` to the orphaned `.mov` file.
* **RAW Sensor Support:** Uses `rawpy` to demosaic and convert uncompressed DSLR/Pro-mode camera files (`.dng`, `.cr2`, etc.) into optimized JPEGs.
* **Active Transcoding & Compression:** Converts heavy smartphone photos to optimized JPEGs and re-encodes bulky videos to H.265 (HEVC) using local CPU power.
* **Zero-Cost Deduplication:** Instantly queries the SQLite B-Tree index to skip previously imported files based on filename, leaving duplicates safely in the staging folder.
* **On-Device Facial Recognition:** Extracts 128-dimensional facial vectors using `dlib` and groups them using the `scikit-learn` DBSCAN algorithm. Identifies unique people entirely offline for easy tagging in the UI.
* **Offline Reverse Geocoding:** Translates raw GPS coordinates into human-readable city and state names without pinging external internet APIs.
* **Blistering Fast UI:** The Flask frontend uses a dedicated `.thumbnails` cache, API-driven autocomplete dropdowns, and database-level pagination to ensure the browser never crashes, even when navigating an archive of 100,000+ files.

---

## 🛠 Prerequisites & Installation

This project is optimized for Linux (Ubuntu/Mint) and relies heavily on FFmpeg for video processing and a C++ compiler for the machine learning models.

**1. Install System Dependencies**

```bash
sudo apt update
sudo apt install ffmpeg cmake

```

**2. Install Python Libraries**

```bash
pip install Pillow pillow-heif Flask reverse_geocoder rawpy exifread face_recognition scikit-learn numpy dlib

```

---

## 🚀 Usage Guide

### 1. Organizing New Media (`organize.py`)

Drop your files (or nested folders of files) into your staging directories (`me`, `shared`, or `misc`). Run the organizer to compress, geocode, sort, thumbnail, scan faces, and index everything.

```bash
python3 organize.py

```

*Note: Video compression is CPU-intensive. Bulk processing 4K videos will take time and utilize high CPU resources.*

### 2. Grouping Faces (`cluster_faces.py`)

After a large bulk import, run the clustering algorithm to group newly discovered faces together based on mathematical similarity. (This is also triggered automatically at the end of `organize.py`).

```bash
python3 cluster_faces.py

```

### 3. The Visual Frontend (`viewer.py`)

Launch the lightweight Flask server to view a searchable, interactive gallery of your media directly in your web browser.

```bash
python3 viewer.py

```

Open `http://127.0.0.1:5000` in Firefox or Chrome to access the gallery.

* **Media Archive:** Search by multi-person tags, location, camera model, or filename using instant API autocomplete. Sort dynamically by Date, Size, or Name.
* **People & Faces:** Switch to the `/people` tab to view unnamed clusters, assign names, and view dedicated galleries for specific people.

### 4. Searching via CLI (`search.py`)

Perform instantaneous indexed searches across your archive directly from the terminal.

```bash
python3 search.py --camera S23 --source shared
python3 search.py --name IMG --flash
python3 search.py --date 2026-05 --gps

```

---

## ⚙️ Advanced Configuration & One-Time Scripts

If you are upgrading an older version of your archive to support new features, **do not re-process your media**. Use the dedicated backfill scripts found in `one_time_scripts/` to safely update your SQLite schema and generate new data:

* **`migrate_locations.py`**: Adds GPS reverse-geocoding to older records.
* **`backfill_thumbs.py`**: Generates 400px JPEG thumbnails/video frames for faster UI loads.
* **`backfill_faces.py`**: A resumable script that scans all existing thumbnails for faces and runs the DBSCAN clustering algorithm.

### Pro-Tip: Shell Aliases

To make the tools accessible globally from your Linux terminal without typing the full path, add these to your `~/.bashrc`:

```bash
alias media-sync="python3 /path/to/media_db/organize.py"
alias media-find="python3 /path/to/media_db/search.py"
alias media-view="python3 /path/to/media_db/viewer.py"

```


