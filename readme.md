# Local Media Archiver & Search Engine

A lightweight, privacy-focused pipeline built for Linux to locally organize, compress, index, and instantly search bulk smartphone media backups. 

Instead of relying on cloud services, this tool uses a local SQLite database to index deep EXIF and video metadata, allowing for instantaneous queries via a Command Line Interface (CLI) or a lightweight local web UI. It features aggressive offline compression, strict chronological sorting, and offline reverse geocoding to keep local storage footprints small while maintaining a highly searchable archive.

## 📂 Project Structure

```text
media_db/
├── organize.py                          # Core engine: Extracts metadata, compresses, moves, and indexes files
├── search.py                            # Fast CLI tool for querying the SQLite database
├── viewer.py                            # Flask web app for visual searching and playback
├── one_time_scripts/
│   └── migrate_locations.py             # Schema updater to retroactively add offline geocoding
└── README.md

```

*Note: The script expects a physical directory structure at `~/everything/personal/backup/` containing `staging/me`, `staging/shared`, `staging/misc`, and an `organized/` folder.*

---

## ✨ Core Features

* **Deep Metadata Extraction:** Reads EXIF data from images (Pillow) and parses hidden moov boxes from videos (FFmpeg/ffprobe) to extract original creation dates, camera hardware models, resolutions, and exposure settings.
* **Active Transcoding & Compression:** * Converts heavy smartphone photos (including HEIC) to highly optimized JPEGs.
* Re-encodes bulky smartphone videos into the highly efficient H.265 (HEVC) codec using local CPU power, strictly retaining the original creation metadata (`-map_metadata 0`).


* **Offline Reverse Geocoding:** Translates raw GPS coordinates into human-readable city and state names (e.g., "Patna, Bihar") without pinging external internet APIs, ensuring location privacy.
* **Bulletproof Sorting:** Bypasses deep nested folders in the staging area to flatten and sort all media perfectly by `YYYY/MM` based on actual hardware timestamps, not file modification dates.

---

## 🛠 Prerequisites & Installation

This project is optimized for Linux (Ubuntu/Mint) and relies heavily on FFmpeg for video processing.

**1. Install System Dependencies**

```bash
sudo apt update
sudo apt install ffmpeg

```

**2. Install Python Libraries**

```bash
pip install Pillow pillow-heif Flask reverse_geocoder

```

---

## 🚀 Usage Guide

### 1. Organizing New Media (`organize.py`)

Drop your files (or nested folders of files) into your staging directories (`me`, `shared`, or `misc`). Run the organizer to compress, geocode, sort, and index everything.

```bash
python3 organize.py

```

*Note: Video compression is CPU-intensive. Bulk processing 4K videos will take time and utilize high CPU resources.*

### 2. Searching via CLI (`search.py`)

Perform instantaneous B-Tree indexed searches across your archive.

```bash
python3 search.py --camera S23 --source shared
python3 search.py --name IMG --flash
python3 search.py --date 2026-05 --gps

```

**Available Flags:** `--name`, `--source` (me/shared/misc), `--date` (YYYY-MM-DD), `--camera`, `--min_size` (in KB), `--flash`, `--gps`.

### 3. The Visual Frontend (`viewer.py`)

Launch the lightweight Flask server to view a searchable, interactive gallery of your media directly in your web browser.

```bash
python3 viewer.py

```

Open `http://127.0.0.1:5000` in Firefox or Chrome to access the gallery. Features lazy-loading for fast rendering of massive image grids and native HTML5 video playback.

---

## ⚙️ Advanced Configuration & One-Time Scripts

### Retroactive Database Upgrades

If you are upgrading an older version of the `media_index.db` to include reverse geocoding, **do not re-process your media**. Run the migration script to safely update the SQLite schema and geocode existing coordinates:

```bash
python3 one_time_scripts/migrate_locations.py
```

### Pro-Tip: Shell Aliases

To make the tools accessible globally from your Linux terminal without typing the full path, add these to your `~/.bashrc`:

```bash
alias media-sync="python3 /path/to/media_db/organize.py"
alias media-find="python3 /path/to/media_db/search.py"
alias media-view="python3 /path/to/media_db/viewer.py"
```
