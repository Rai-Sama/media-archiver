from flask import Flask, request, render_template_string, send_file
import sqlite3
from pathlib import Path
import os
import urllib.parse

app = Flask(__name__)

DB_PATH = Path.home() / "everything/personal/backup/media_index.db"

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
        .filter-row { display: flex; gap: 15px; flex-wrap: wrap; align-items: center; }
        .filter-label { font-size: 0.85em; color: #aaa; margin-bottom: 4px; display: block; text-transform: uppercase; letter-spacing: 0.5px; }
        
        input[type="text"], input[type="date"], select { 
            padding: 10px; background: #2a2a2a; color: white; border: 1px solid #444; border-radius: 6px; outline: none; min-width: 150px;
        }
        input:focus, select:focus { border-color: #007bff; }
        
        .checkbox-group { display: flex; gap: 15px; background: #2a2a2a; padding: 10px 15px; border-radius: 6px; border: 1px solid #444; }
        .checkbox-group label { cursor: pointer; display: flex; align-items: center; gap: 6px; font-size: 0.9em; }
        
        button { cursor: pointer; background: #007bff; color: white; padding: 10px 20px; font-weight: bold; border: none; border-radius: 6px; }
        button:hover { background: #0056b3; }
        .clear-btn { padding: 10px 15px; background: #444; color: white; text-decoration: none; border-radius: 6px; font-size: 0.9em; }
        .clear-btn:hover { background: #555; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 15px; }
        .card { background: #1e1e1e; border-radius: 8px; overflow: hidden; border: 1px solid #333; transition: transform 0.1s; }
        .card:hover { border-color: #555; }
        
        /* Turn the entire container into a clickable button */
        .media-container { 
            height: 200px; width: 100%; background: #0b0b0b; display: flex; align-items: center; justify-content: center; overflow: hidden;
            cursor: pointer; position: relative;
        }
        /* Make the inner media ignore mouse events so the container registers the click */
        .media-container img, .media-container video { 
            width: 100%; height: 100%; object-fit: cover; pointer-events: none; transition: transform 0.2s; 
        }
        .media-container:hover img, .media-container:hover video { transform: scale(1.03); opacity: 0.8; }
        
        /* Play Icon Overlay for Videos in Grid */
        .play-icon {
            position: absolute; font-size: 3em; color: rgba(255, 255, 255, 0.7); pointer-events: none;
        }

        .info { padding: 12px; font-size: 0.85em; color: #ccc; line-height: 1.5; }
        .badge { display: inline-block; padding: 2px 6px; background: #333; border-radius: 4px; font-size: 0.8em; margin-bottom: 6px; font-weight: bold; }
        .badge.src-me { background: #1e4b35; color: #a3e4c4; }
        .badge.src-shared { background: #4b351e; color: #e4c4a3; }
        .badge.src-misc { background: #351e4b; color: #c4a3e4; }

        /* Advanced Modal / Lightbox Styles */
        .modal { 
            display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; 
            background-color: rgba(0,0,0,0.95); justify-content: center; align-items: center; backdrop-filter: blur(5px);
        }
        .modal-content { max-width: 90%; max-height: 90vh; object-fit: contain; border-radius: 4px; box-shadow: 0 4px 25px rgba(0,0,0,0.8); display: none; }
        
        /* Navigation Controls */
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
                <div>
                    <span class="filter-label">Primary Source</span>
                    <select name="source">
                        <option value="">All Sources</option>
                        <option value="me" {% if request.args.get('source') == 'me' %}selected{% endif %}>My Camera (me)</option>
                        <option value="shared" {% if request.args.get('source') == 'shared' %}selected{% endif %}>Shared</option>
                        <option value="misc" {% if request.args.get('source') == 'misc' %}selected{% endif %}>Miscellaneous</option>
                    </select>
                </div>
                <div>
                    <span class="filter-label">Start Date</span>
                    <input type="date" name="start_date" value="{{ request.args.get('start_date', '') }}">
                </div>
                <div>
                    <span class="filter-label">End Date</span>
                    <input type="date" name="end_date" value="{{ request.args.get('end_date', '') }}">
                </div>
                <div>
                    <span class="filter-label">Camera Model</span>
                    <input type="text" name="camera" placeholder="e.g., SM-S911B" value="{{ request.args.get('camera', '') }}">
                </div>
                <div>
                    <span class="filter-label">Location</span>
                    <input type="text" name="location" placeholder="City or State..." value="{{ request.args.get('location', '') }}">
                </div>
            </div>
            
            <div class="filter-row" style="margin-top: 5px;">
                <div>
                    <input type="text" name="name" placeholder="Filename snippet..." value="{{ request.args.get('name', '') }}">
                </div>
                <div>
                    <select name="file_type">
                        <option value="">All File Types</option>
                        <option value="image" {% if request.args.get('file_type') == 'image' %}selected{% endif %}>Images Only</option>
                        <option value="video" {% if request.args.get('file_type') == 'video' %}selected{% endif %}>Videos Only</option>
                        <option value="document" {% if request.args.get('file_type') == 'document' %}selected{% endif %}>Documents Only</option>
                    </select>
                </div>
                <div class="checkbox-group">
                    <label><input type="checkbox" name="has_gps" value="1" {% if request.args.get('has_gps') == '1' %}checked{% endif %}> 📍 Has GPS Location</label>
                    <label><input type="checkbox" name="flash" value="1" {% if request.args.get('flash') == '1' %}checked{% endif %}> ⚡ Flash Fired</label>
                </div>
                
                <div style="flex-grow: 1; display: flex; justify-content: flex-end; gap: 10px;">
                    <a href="/" class="clear-btn">Reset</a>
                    <button type="submit">Execute Search</button>
                </div>
            </div>
        </form>
    </div>
    
    <div class="grid">
        {% for item in results %}
        <div class="card">
            <div class="media-container" onclick="openLightbox({{ loop.index0 }})">
                {% if item.file_type == 'image' %}
                    <img src="/file?path={{ item.current_path | urlencode }}" loading="lazy" alt="{{ item.original_name }}">
                {% elif item.file_type == 'video' %}
                    <video src="/file?path={{ item.current_path | urlencode }}#t=0.1" preload="metadata"></video>
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

    <div id="lightboxModal" class="modal" onclick="closeLightbox()">
        <span class="counter" id="modalCounter"></span>
        <span class="modal-close">&times;</span>
        
        <div class="nav-btn prev-btn" onclick="navigate(-1, event)">&#10094;</div>
        
        <img class="modal-content" id="modalImg" onclick="event.stopPropagation();">
        <video class="modal-content" id="modalVid" controls onclick="event.stopPropagation();"></video>
        
        <div class="nav-btn next-btn" onclick="navigate(1, event)">&#10095;</div>
    </div>

    <script>
        // Inject the search results dynamically into a Javascript array
        const galleryData = [
            {% for item in results %}
            {
                type: "{{ item.file_type }}",
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
            
            // Skip documents entirely in gallery view
            if (galleryData[index].type === 'document') {
                return;
            }

            currentIndex = index;
            const item = galleryData[currentIndex];

            // Reset visibility and pause any playing video
            modalImg.style.display = 'none';
            modalVid.style.display = 'none';
            modalVid.pause();

            if (item.type === 'image') {
                modalImg.src = item.src;
                modalImg.style.display = 'block';
            } else if (item.type === 'video') {
                modalVid.src = item.src;
                modalVid.style.display = 'block';
                modalVid.play(); // Auto-play video when navigated to
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
            if (event) event.stopPropagation(); // Prevents background click from closing modal
            
            let nextIndex = currentIndex + direction;
            
            // Fast-forward past documents if they exist in the sequence
            while (nextIndex >= 0 && nextIndex < galleryData.length && galleryData[nextIndex].type === 'document') {
                nextIndex += direction;
            }
            
            // Loop around the gallery
            if (nextIndex >= galleryData.length) nextIndex = 0;
            if (nextIndex < 0) nextIndex = galleryData.length - 1;
            
            openLightbox(nextIndex);
        }

        // Listen for Keyboard Events
        document.addEventListener('keydown', function(event) {
            if (modal.style.display === 'flex') {
                if (event.key === "Escape") closeLightbox();
                else if (event.key === "ArrowRight") navigate(1, null);
                else if (event.key === "ArrowLeft") navigate(-1, null);
            }
        });
        // --- Date Filter Linking Logic ---
        const startDateInput = document.querySelector('input[name="start_date"]');
        const endDateInput = document.querySelector('input[name="end_date"]');

        function updateBounds() {
            // Keeps the logical min/max bounds so you can't search negative ranges
            if (startDateInput.value) endDateInput.min = startDateInput.value;
            else endDateInput.min = "";
            
            if (endDateInput.value) startDateInput.max = endDateInput.value;
            else startDateInput.max = "";
        }

        startDateInput.addEventListener('change', function() {
            // Auto-fill the end date if it is currently empty
            if (this.value && !endDateInput.value) {
                endDateInput.value = this.value;
            }
            updateBounds();
        });

        endDateInput.addEventListener('change', function() {
            // Auto-fill the start date if it is currently empty
            if (this.value && !startDateInput.value) {
                startDateInput.value = this.value;
            }
            updateBounds();
        });
        
        // Run once on page load
        updateBounds();
   </script>
</body>
</html>
"""

# Register custom urlencode filter for the Jinja template
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

@app.route("/")
def index():
    source = request.args.get("source", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    camera = request.args.get("camera", "")
    location = request.args.get("location", "")
    
    name = request.args.get("name", "")
    file_type = request.args.get("file_type", "")
    has_gps = request.args.get("has_gps", "")
    flash = request.args.get("flash", "")
    
    conn = get_db_connection()
    query = """
        SELECT original_name, current_path, file_type, source, 
               date_taken, camera_model, file_size_kb, location_name 
        FROM media WHERE 1=1
    """
    params = []
    
    if source:
        query += " AND source = ?"
        params.append(source)
    if camera:
        query += " AND camera_model LIKE ?"
        params.append(f"%{camera}%")
    if location:
        query += " AND location_name LIKE ?"
        params.append(f"%{location}%")
        
    if start_date:
        query += " AND date_taken >= ?"
        params.append(start_date + " 00:00:00")
    if end_date:
        query += " AND date_taken <= ?"
        params.append(end_date + " 23:59:59")

    if name:
        query += " AND original_name LIKE ?"
        params.append(f"%{name}%")
    if file_type:
        query += " AND file_type = ?"
        params.append(file_type)
    if has_gps == "1":
        query += " AND latitude IS NOT NULL"
    if flash == "1":
        query += " AND flash_fired = 1"
        
    query += " ORDER BY date_taken DESC LIMIT 200"
    
    results = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template_string(HTML_TEMPLATE, results=results)

@app.route("/file")
def serve_file():
    file_path = request.args.get("path")
    if file_path and os.path.exists(file_path):
        return send_file(file_path)
    return "File not found", 404

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
