from flask import Flask, request, render_template_string, send_file, jsonify
import sqlite3
from pathlib import Path
import os
import urllib.parse
import json
import hashlib
import subprocess
from PIL import Image, ImageOps

app = Flask(__name__)

# --- Directory Setup ---
BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"
THUMB_DIR = BASE_DIR / ".thumbnails"

# Ensure the hidden cache directory exists
THUMB_DIR.mkdir(parents=True, exist_ok=True)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Local Media Archive</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #121212; color: #e0e0e0; padding: 20px; margin: 0; }
        .header-container { background: #1e1e1e; padding: 20px; border-radius: 8px; margin-bottom: 25px; border: 1px solid #333; }
        h2 { margin-top: 0; color: #fff; }
        
        .search-form { display: flex; flex-direction: column; gap: 15px; }
        .filter-row { display: flex; gap: 15px; flex-wrap: wrap; align-items: flex-end; }
        .filter-label { font-size: 0.85em; color: #aaa; margin-bottom: 4px; display: block; text-transform: uppercase; letter-spacing: 0.5px; }
        
        input[type="text"], input[type="date"], select { 
            padding: 10px; background: #2a2a2a; color: white; border: 1px solid #444; border-radius: 6px; outline: none; min-width: 150px;
            box-sizing: border-box;
        }
        input:focus, select:focus { border-color: #007bff; }
        input::-webkit-calendar-picker-indicator { opacity: 1; cursor: pointer; filter: invert(0.8); }
        
        .checkbox-group { display: flex; gap: 15px; background: #2a2a2a; padding: 10px 15px; border-radius: 6px; border: 1px solid #444; height: 40px; box-sizing: border-box;}
        .checkbox-group label { cursor: pointer; display: flex; align-items: center; gap: 6px; font-size: 0.9em; }
        
        button { cursor: pointer; background: #007bff; color: white; padding: 10px 20px; font-weight: bold; border: none; border-radius: 6px; height: 40px; box-sizing: border-box;}
        button:hover:not(:disabled) { background: #0056b3; }
        .clear-btn { padding: 10px 15px; background: #444; color: white; text-decoration: none; border-radius: 6px; font-size: 0.9em; height: 40px; box-sizing: border-box; display: flex; align-items: center; justify-content: center;}
        .clear-btn:hover { background: #555; }

        .input-group { display: flex; flex-direction: column; }
        .autocomplete-wrapper { position: relative; }
        .autocomplete-dropdown {
            position: absolute; top: 100%; left: 0; z-index: 999;
            width: max-content; min-width: 100%; max-width: 400px; max-height: 250px; overflow-y: auto;
            background-color: #2a2a2a; border: 1px solid #444; border-radius: 4px; 
            box-shadow: 0 8px 16px rgba(0,0,0,0.8); display: none; margin-top: 4px;
        }
        .autocomplete-item { padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #333; word-break: break-all; color: #fff; font-size: 0.9em;}
        .autocomplete-item:hover { background-color: #007bff; }
        .autocomplete-item:last-child { border-bottom: none; }
        .loading-spinner { display: none; position: absolute; right: 10px; top: 50%; transform: translateY(-50%); color: #888; font-size: 0.8em; pointer-events: none; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 15px; }
        .card { background: #1e1e1e; border-radius: 8px; overflow: hidden; border: 1px solid #333; transition: transform 0.1s; }
        .card:hover { border-color: #555; }
        
        .media-container { 
            height: 200px; width: 100%; background: #0b0b0b; display: flex; align-items: center; justify-content: center; overflow: hidden;
            cursor: pointer; position: relative;
        }
        .media-container img { 
            width: 100%; height: 100%; object-fit: cover; pointer-events: none; transition: transform 0.2s; 
        }
        .media-container:hover img { transform: scale(1.03); opacity: 0.8; }
        .play-icon { position: absolute; font-size: 3em; color: rgba(255, 255, 255, 0.7); pointer-events: none; }

        .info { padding: 12px; font-size: 0.85em; color: #ccc; line-height: 1.5; }
        .badge { display: inline-block; padding: 2px 6px; background: #333; border-radius: 4px; font-size: 0.8em; margin-bottom: 6px; font-weight: bold; }
        .badge.src-me { background: #1e4b35; color: #a3e4c4; }
        .badge.src-shared { background: #4b351e; color: #e4c4a3; }
        .badge.src-misc { background: #351e4b; color: #c4a3e4; }

        .pagination { display: flex; justify-content: center; align-items: center; gap: 15px; margin-top: 30px; padding-bottom: 20px; }
        .page-btn { padding: 10px 20px; background: #2a2a2a; color: #fff; border: 1px solid #444; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.2s; }
        .page-btn:hover:not(:disabled) { background: #007bff; border-color: #007bff; }
        .page-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .page-info { color: #aaa; font-size: 0.9em; font-family: monospace; }

        .modal { 
            display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; 
            background-color: rgba(0,0,0,0.95); justify-content: center; align-items: center; backdrop-filter: blur(5px);
        }
        .modal-content { max-width: 90%; max-height: 90vh; object-fit: contain; border-radius: 4px; box-shadow: 0 4px 25px rgba(0,0,0,0.8); display: none; }
        .modal-close { position: absolute; top: 20px; right: 30px; color: #fff; font-size: 40px; font-weight: bold; cursor: pointer; user-select: none; z-index: 1001; }
        .nav-btn { position: absolute; top: 50%; transform: translateY(-50%); color: #fff; font-size: 50px; cursor: pointer; user-select: none; padding: 20px; z-index: 1001; transition: 0.2s; }
        .nav-btn:hover { color: #007bff; }
        .prev-btn { left: 10px; }
        .next-btn { right: 10px; }
        .counter { position: absolute; top: 25px; left: 30px; color: #aaa; font-size: 1.2em; font-family: monospace; }
    </style>
</head>
<body>

    <div class="header-container">
        <h2>📷 Media Archive Search</h2>
        <form class="search-form" method="GET" action="/">
            
            <div class="filter-row">
                <div class="input-group">
                    <span class="filter-label">Primary Source</span>
                    <select name="source">
                        <option value="">All Sources</option>
                        <option value="me" {% if request.args.get('source') == 'me' %}selected{% endif %}>My Camera</option>
                        <option value="shared" {% if request.args.get('source') == 'shared' %}selected{% endif %}>Shared</option>
                        <option value="misc" {% if request.args.get('source') == 'misc' %}selected{% endif %}>Misc</option>
                    </select>
                </div>
                
                <div class="input-group">
                    <span class="filter-label">Start Date</span>
                    <input type="date" name="start_date" value="{{ request.args.get('start_date', '') }}">
                </div>
                
                <div class="input-group">
                    <span class="filter-label">End Date</span>
                    <input type="date" name="end_date" value="{{ request.args.get('end_date', '') }}">
                </div>
                
                <div class="input-group">
                    <span class="filter-label">Camera Model</span>
                    <div class="autocomplete-wrapper">
                        <input type="text" id="cameraInput" name="camera" placeholder="e.g., SM-S911B" value="{{ request.args.get('camera', '') }}" autocomplete="off" style="width: 180px;">
                        <span id="cameraLoader" class="loading-spinner">⏳</span>
                        <div id="cameraDropdown" class="autocomplete-dropdown"></div>
                    </div>
                </div>
                
                <div class="input-group">
                    <span class="filter-label">Location</span>
                    <div class="autocomplete-wrapper">
                        <input type="text" id="locationInput" name="location" placeholder="City or State..." value="{{ request.args.get('location', '') }}" autocomplete="off" style="width: 200px;">
                        <span id="locationLoader" class="loading-spinner">⏳</span>
                        <div id="locationDropdown" class="autocomplete-dropdown"></div>
                    </div>
                </div>
            </div>
            
            <div class="filter-row">
                <div class="input-group">
                    <span class="filter-label">File Name</span>
                    <div class="autocomplete-wrapper">
                        <input type="text" id="filenameInput" name="name" placeholder="Exact filename snippet..." value="{{ request.args.get('name', '') }}" autocomplete="off" style="min-width: 200px;">
                        <span id="filenameLoader" class="loading-spinner">⏳</span>
                        <div id="filenameDropdown" class="autocomplete-dropdown"></div>
                    </div>
                </div>

                <div class="input-group">
                    <span class="filter-label">File Type</span>
                    <select name="file_type">
                        <option value="">All File Types</option>
                        <option value="image" {% if request.args.get('file_type') == 'image' %}selected{% endif %}>Images Only</option>
                        <option value="video" {% if request.args.get('file_type') == 'video' %}selected{% endif %}>Videos Only</option>
                        <option value="document" {% if request.args.get('file_type') == 'document' %}selected{% endif %}>Documents Only</option>
                    </select>
                </div>
                
                <div class="checkbox-group">
                    <label><input type="checkbox" name="has_gps" value="1" {% if request.args.get('has_gps') == '1' %}checked{% endif %}> 📍 GPS</label>
                    <label><input type="checkbox" name="flash" value="1" {% if request.args.get('flash') == '1' %}checked{% endif %}> ⚡ Flash</label>
                </div>
                
                <div style="display: flex; flex-grow: 1; justify-content: flex-end; gap: 10px;">
                    <a href="/" class="clear-btn">Reset</a>
                    <button type="submit">Search</button>
                </div>
            </div>
        </form>
    </div>
    
    <div class="grid">
        {% for item in results %}
        <div class="card">
            <div class="media-container" onclick="openLightbox({{ loop.index0 }})">
                {% if item.file_type == 'image' %}
                    <img src="/thumbnail?path={{ item.current_path | urlencode }}&type=image" loading="lazy" alt="{{ item.original_name }}">
                {% elif item.file_type == 'video' %}
                    <img src="/thumbnail?path={{ item.current_path | urlencode }}&type=video" loading="lazy" alt="{{ item.original_name }}">
                    <div class="play-icon">▶</div>
                {% else %}
                    <div style="color: #666; font-size: 3em;">📄</div>
                {% endif %}
            </div>
            <div class="info">
                <div class="badge src-{{ item.source }}">{{ item.source | upper }}</div>
                {% if item.camera_model %}<div class="badge" style="background:#2b4b6f;">{{ item.camera_model[:15] }}</div>{% endif %}
                {% if item.location_name %}<div class="badge" style="background:#8b0000; color:#ffcccc;">📍 {{ item.location_name }}</div>{% endif %}
                <br>
                <strong style="color: #fff; word-break: break-all;">{{ item.original_name[:30] }}</strong><br>
                <span style="color: #999;">{{ item.date_taken if item.date_taken else 'Unknown Date' }}</span><br>
                <span style="color: #00bfff;">{{ item.file_size_kb }} KB</span>
            </div>
        </div>
        {% else %}
            <p style="color: #888; grid-column: 1 / -1; text-align: center; padding: 40px;">No media found matching your exact parameters.</p>
        {% endfor %}
    </div>

    {% if total_pages > 0 %}
    <div class="pagination">
        <button class="page-btn" onclick="changePage({{ page - 1 }})" {% if page <= 1 %}disabled{% endif %}>&#10094; Previous</button>
        <span class="page-info">Page {{ page }} of {{ total_pages }} ({{ total_count }} items)</span>
        <button class="page-btn" onclick="changePage({{ page + 1 }})" {% if page >= total_pages %}disabled{% endif %}>Next &#10095;</button>
    </div>
    {% endif %}

    <div id="lightboxModal" class="modal" onclick="closeLightbox()">
        <span class="counter" id="modalCounter"></span>
        <span class="modal-close">&times;</span>
        <div class="nav-btn prev-btn" onclick="navigate(-1, event)">&#10094;</div>
        <img class="modal-content" id="modalImg" onclick="event.stopPropagation();">
        <video class="modal-content" id="modalVid" controls onclick="event.stopPropagation();"></video>
        <div class="nav-btn next-btn" onclick="navigate(1, event)">&#10095;</div>
    </div>

    <script>
        function changePage(newPage) {
            const url = new URL(window.location.href);
            url.searchParams.set('page', newPage);
            window.location.href = url.toString();
        }

        function setupApiAutocomplete(inputId, dropdownId, dbColumn) {
            const inputEl = document.getElementById(inputId);
            const dropdownEl = document.getElementById(dropdownId);
            const loaderEl = document.getElementById(inputId.replace('Input', 'Loader'));
            let timeoutId;

            if (!inputEl || !dropdownEl) return;

            inputEl.addEventListener("input", function() {
                clearTimeout(timeoutId);
                const val = this.value.trim();
                
                if (!val) {
                    dropdownEl.style.display = "none";
                    if (loaderEl) loaderEl.style.display = "none";
                    return;
                }

                if (loaderEl) loaderEl.style.display = "block";

                timeoutId = setTimeout(async () => {
                    try {
                        const response = await fetch(`/api/suggest?column=${dbColumn}&q=${encodeURIComponent(val)}`);
                        if (!response.ok) throw new Error('Network response was not ok');
                        
                        const dataArray = await response.json();
                        dropdownEl.innerHTML = ""; 

                        if (dataArray.length === 0) {
                            dropdownEl.style.display = "none";
                        } else {
                            dataArray.forEach(itemText => {
                                const itemDiv = document.createElement("div");
                                itemDiv.className = "autocomplete-item";
                                itemDiv.innerText = itemText;
                                
                                itemDiv.addEventListener("click", function() {
                                    inputEl.value = this.innerText;
                                    dropdownEl.style.display = "none";
                                });
                                
                                dropdownEl.appendChild(itemDiv);
                            });
                            dropdownEl.style.display = "block";
                        }
                    } catch (error) {
                        console.error('Fetch error:', error);
                        dropdownEl.style.display = "none";
                    } finally {
                        if (loaderEl) loaderEl.style.display = "none";
                    }
                }, 150); 
            });

            document.addEventListener("click", function (e) {
                if (e.target !== inputEl && e.target !== dropdownEl) {
                    dropdownEl.style.display = "none";
                }
            });
        }

        setupApiAutocomplete("filenameInput", "filenameDropdown", "original_name");
        setupApiAutocomplete("cameraInput", "cameraDropdown", "camera_model");
        setupApiAutocomplete("locationInput", "locationDropdown", "location_name");

        const galleryData = [
            {% for item in results %}
            {
                type: "{{ item.file_type }}",
                // The lightbox still requests the original full resolution /file
                src: "/file?path={{ item.current_path | urlencode }}" 
            }{% if not loop.last %},{% endif %}
            {% endfor %}
        ];

        let currentIndex = 0;
        const modal = document.getElementById('lightboxModal');
        const modalImg = document.getElementById('modalImg');
        const modalVid = document.getElementById('modalVid');
        const counter = document.getElementById('modalCounter');

        function openLightbox(index) {
            if (index < 0 || index >= galleryData.length) return;
            if (galleryData[index].type === 'document') return;

            currentIndex = index;
            const item = galleryData[currentIndex];

            modalImg.style.display = 'none';
            modalVid.style.display = 'none';
            modalVid.pause();

            if (item.type === 'image') {
                modalImg.src = item.src;
                modalImg.style.display = 'block';
            } else if (item.type === 'video') {
                modalVid.src = item.src;
                modalVid.style.display = 'block';
                modalVid.play();
            }

            counter.innerText = `${currentIndex + 1} / ${galleryData.length}`;
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }

        function closeLightbox() {
            modal.style.display = 'none';
            modalVid.pause();
            modalVid.src = '';
            modalImg.src = '';
            document.body.style.overflow = 'auto';
        }

        function navigate(direction, event) {
            if (event) event.stopPropagation();
            let nextIndex = currentIndex + direction;
            while (nextIndex >= 0 && nextIndex < galleryData.length && galleryData[nextIndex].type === 'document') {
                nextIndex += direction;
            }
            if (nextIndex >= galleryData.length) nextIndex = 0;
            if (nextIndex < 0) nextIndex = galleryData.length - 1;
            openLightbox(nextIndex);
        }

        document.addEventListener('keydown', function(event) {
            if (modal.style.display === 'flex') {
                if (event.key === "Escape") closeLightbox();
                else if (event.key === "ArrowRight") navigate(1, null);
                else if (event.key === "ArrowLeft") navigate(-1, null);
            }
        });

        const startDateInput = document.querySelector('input[name="start_date"]');
        const endDateInput = document.querySelector('input[name="end_date"]');

        function updateBounds() {
            if (startDateInput.value) endDateInput.min = startDateInput.value;
            else endDateInput.min = "";
            
            if (endDateInput.value) startDateInput.max = endDateInput.value;
            else startDateInput.max = "";
        }

        startDateInput.addEventListener('change', function() {
            if (this.value && !endDateInput.value) {
                endDateInput.value = this.value;
            }
            updateBounds();
        });

        endDateInput.addEventListener('change', function() {
            if (this.value && !startDateInput.value) {
                startDateInput.value = this.value;
            }
            updateBounds();
        });
        
        updateBounds();
    </script>
</body>
</html>
"""

@app.template_filter('urlencode')
def urlencode_filter(s):
    if type(s) == 'Markup':
        s = s.unescape()
    s = s.encode('utf8')
    s = urllib.parse.quote_plus(s)
    return s

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/api/suggest")
def api_suggest():
    column = request.args.get("column")
    query_str = request.args.get("q", "")
    valid_columns = {"original_name", "camera_model", "location_name"}
    
    if column not in valid_columns or not query_str:
        return jsonify([])
        
    conn = get_db_connection()
    query = f"SELECT DISTINCT {column} FROM media WHERE {column} LIKE ? ORDER BY {column} LIMIT 20"
    results = conn.execute(query, (f"%{query_str}%",)).fetchall()
    conn.close()
    
    suggestions = [row[0] for row in results if row[0]]
    return jsonify(suggestions)

# --- NEW: On-The-Fly Thumbnail Generator ---
@app.route("/thumbnail")
def serve_thumbnail():
    file_path = request.args.get("path")
    file_type = request.args.get("type", "image")
    
    if not file_path or not os.path.exists(file_path):
        return "Not found", 404
        
    # Generate a unique filename for the cache based on the absolute path
    path_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
    cache_path = THUMB_DIR / f"{path_hash}.jpg"
    
    # 1. If we already made it previously, serve it instantly
    if cache_path.exists():
        return send_file(cache_path)
        
    # 2. Generate Photo Thumbnail
    if file_type == "image":
        try:
            with Image.open(file_path) as img:
                # Corrects orientation if the phone took the photo sideways
                img = ImageOps.exif_transpose(img) 
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                # Resize down to a max bounding box of 400x400
                img.thumbnail((400, 400))
                img.save(cache_path, "JPEG", quality=75)
            return send_file(cache_path)
        except Exception:
            return send_file(file_path) # Fallback to original if Pillow fails
            
    # 3. Generate Video Thumbnail (Rips the frame at the 0.1 second mark)
    elif file_type == "video":
        try:
            cmd = [
                "ffmpeg", "-y", "-i", file_path, 
                "-ss", "00:00:00.100", "-vframes", "1", 
                "-vf", "scale=400:-1", str(cache_path)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return send_file(cache_path)
        except Exception:
            # Fallback to the original file to prevent a broken image icon
            return send_file(file_path)

@app.route("/")
def index():
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1

    source = request.args.get("source", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    camera = request.args.get("camera", "")
    location = request.args.get("location", "")
    
    name = request.args.get("name", "")
    file_type = request.args.get("file_type", "")
    has_gps = request.args.get("has_gps", "")
    flash = request.args.get("flash", "")
    
    conditions = ""
    params = []
    
    if source:
        conditions += " AND source = ?"
        params.append(source)
    if camera:
        conditions += " AND camera_model LIKE ?"
        params.append(f"%{camera}%")
    if location:
        conditions += " AND location_name LIKE ?"
        params.append(f"%{location}%")
        
    if start_date:
        conditions += " AND date_taken >= ?"
        params.append(start_date + " 00:00:00")
    if end_date:
        conditions += " AND date_taken <= ?"
        params.append(end_date + " 23:59:59")

    if name:
        conditions += " AND original_name LIKE ?"
        params.append(f"%{name}%")
    if file_type:
        conditions += " AND file_type = ?"
        params.append(file_type)
    if has_gps == "1":
        conditions += " AND latitude IS NOT NULL"
    if flash == "1":
        conditions += " AND flash_fired = 1"

    conn = get_db_connection()
    
    count_query = f"SELECT COUNT(*) FROM media WHERE 1=1 {conditions}"
    total_count = conn.execute(count_query, params).fetchone()[0]
    
    per_page = 200
    total_pages = (total_count + per_page - 1) // per_page
    
    if total_pages == 0: total_pages = 1
    if page < 1: page = 1
    elif page > total_pages: page = total_pages
        
    offset = (page - 1) * per_page
    
    data_query = f"""
        SELECT original_name, current_path, file_type, source, 
               date_taken, camera_model, file_size_kb, location_name 
        FROM media WHERE 1=1 {conditions}
        ORDER BY date_taken DESC LIMIT {per_page} OFFSET ?
    """
    
    params.append(offset)
    results = conn.execute(data_query, params).fetchall()
    
    conn.close()
    
    return render_template_string(
        HTML_TEMPLATE, 
        results=results, 
        page=page, 
        total_pages=total_pages, 
        total_count=total_count
    )

@app.route("/file")
def serve_file():
    file_path = request.args.get("path")
    if file_path and os.path.exists(file_path):
        return send_file(file_path)
    return "File not found", 404

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
