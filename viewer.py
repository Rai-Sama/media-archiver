from flask import Flask, request, render_template_string, send_file, jsonify
import sqlite3
from pathlib import Path
import os
import urllib.parse
import hashlib
import subprocess
from PIL import Image, ImageOps

app = Flask(__name__)

# --- Directory Setup ---
BASE_DIR = Path.home() / "everything/personal/backup"
DB_PATH = BASE_DIR / "media_index.db"
THUMB_DIR = BASE_DIR / ".thumbnails"
THUMB_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# TEMPLATE 1: MAIN MEDIA ARCHIVE
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Local Media Archive</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #121212; color: #e0e0e0; padding: 20px; margin: 0; }
        
        /* Navigation Bar */
        .top-nav { display: flex; gap: 20px; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333; }
        .top-nav a { color: #888; text-decoration: none; font-size: 1.2em; font-weight: bold; transition: color 0.2s; }
        .top-nav a.active { color: #00bfff; }
        .top-nav a:hover { color: #fff; }

        .header-container { background: #1e1e1e; padding: 20px; border-radius: 8px; margin-bottom: 25px; border: 1px solid #333; }
        .search-form { display: flex; flex-direction: column; gap: 15px; }
        .filter-row { display: flex; gap: 15px; flex-wrap: wrap; align-items: flex-end; }
        .filter-label { font-size: 0.85em; color: #aaa; margin-bottom: 4px; display: block; text-transform: uppercase; letter-spacing: 0.5px; }
        
        input[type="text"], input[type="date"], select { 
            padding: 10px; background: #2a2a2a; color: white; border: 1px solid #444; border-radius: 6px; outline: none; min-width: 150px; box-sizing: border-box;
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
            position: absolute; top: 100%; left: 0; z-index: 999; width: max-content; min-width: 100%; max-width: 400px; max-height: 250px; overflow-y: auto; background-color: #2a2a2a; border: 1px solid #444; border-radius: 4px; box-shadow: 0 8px 16px rgba(0,0,0,0.8); display: none; margin-top: 4px;
        }
        .autocomplete-item { padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #333; word-break: break-all; color: #fff; font-size: 0.9em;}
        .autocomplete-item:hover { background-color: #007bff; }
        .autocomplete-item:last-child { border-bottom: none; }
        .loading-spinner { display: none; position: absolute; right: 10px; top: 50%; transform: translateY(-50%); color: #888; font-size: 0.8em; pointer-events: none; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 15px; }
        .card { background: #1e1e1e; border-radius: 8px; overflow: hidden; border: 1px solid #333; transition: transform 0.1s; }
        .card:hover { border-color: #555; }
        
        .media-container { height: 200px; width: 100%; background: #0b0b0b; display: flex; align-items: center; justify-content: center; overflow: hidden; cursor: pointer; position: relative; }
        .media-container img { width: 100%; height: 100%; object-fit: cover; pointer-events: none; transition: transform 0.2s; }
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

        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.95); justify-content: center; align-items: center; backdrop-filter: blur(5px); }
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

    <div class="top-nav">
        <a href="/" class="active">📷 Media Archive</a>
        <a href="/people">👥 People & Faces</a>
    </div>

    <div class="header-container">
        <form class="search-form" method="GET" action="/">
            
            <div class="filter-row">
                <div class="input-group">
                    <span class="filter-label">Person</span>
                    <div class="autocomplete-wrapper">
                        <input type="text" id="personInput" name="person" placeholder="e.g., Anshuman" value="{{ request.args.get('person', '') }}" autocomplete="off" style="width: 180px; border-color: #00bfff;">
                        <span id="personLoader" class="loading-spinner">⏳</span>
                        <div id="personDropdown" class="autocomplete-dropdown"></div>
                    </div>
                </div>

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
                        <input type="text" id="cameraInput" name="camera" placeholder="e.g., SM-S911B" value="{{ request.args.get('camera', '') }}" autocomplete="off" style="width: 160px;">
                        <span id="cameraLoader" class="loading-spinner">⏳</span>
                        <div id="cameraDropdown" class="autocomplete-dropdown"></div>
                    </div>
                </div>
            </div>
            
            <div class="filter-row">
                <div class="input-group">
                    <span class="filter-label">Location</span>
                    <div class="autocomplete-wrapper">
                        <input type="text" id="locationInput" name="location" placeholder="City or State..." value="{{ request.args.get('location', '') }}" autocomplete="off" style="width: 180px;">
                        <span id="locationLoader" class="loading-spinner">⏳</span>
                        <div id="locationDropdown" class="autocomplete-dropdown"></div>
                    </div>
                </div>

                <div class="input-group">
                    <span class="filter-label">File Name</span>
                    <div class="autocomplete-wrapper">
                        <input type="text" id="filenameInput" name="name" placeholder="Exact filename snippet..." value="{{ request.args.get('name', '') }}" autocomplete="off" style="min-width: 180px;">
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
                
                <div class="input-group" style="width: 160px;">
                    <span class="filter-label">Sort By</span>
                    <select name="sort">
                        <option value="date_desc" {% if request.args.get('sort') == 'date_desc' or not request.args.get('sort') %}selected{% endif %}>Date (Newest)</option>
                        <option value="date_asc" {% if request.args.get('sort') == 'date_asc' %}selected{% endif %}>Date (Oldest)</option>
                        <option value="size_desc" {% if request.args.get('sort') == 'size_desc' %}selected{% endif %}>Size (Largest)</option>
                        <option value="size_asc" {% if request.args.get('sort') == 'size_asc' %}selected{% endif %}>Size (Smallest)</option>
                    </select>
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
                    <img src="/thumbnail?path={{ item.current_path | urlencode }}&type=image" loading="lazy">
                {% elif item.file_type == 'video' %}
                    <img src="/thumbnail?path={{ item.current_path | urlencode }}&type=video" loading="lazy">
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

        // --- UPGRADED: Multi-Select & Focus-to-Show Autocomplete Engine ---
        function setupApiAutocomplete(inputId, dropdownId, apiEndpoint, isMulti = false) {
            const inputEl = document.getElementById(inputId);
            const dropdownEl = document.getElementById(dropdownId);
            const loaderEl = document.getElementById(inputId.replace('Input', 'Loader'));
            let timeoutId;

            if (!inputEl || !dropdownEl) return;

            async function fetchSuggestions(searchQuery) {
                if (loaderEl) loaderEl.style.display = "block";
                try {
                    const url = new URL(apiEndpoint, window.location.origin);
                    if (searchQuery) url.searchParams.set('q', searchQuery);
                    
                    const response = await fetch(url);
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
                            
                            itemDiv.addEventListener("click", function(e) {
                                if (isMulti) {
                                    // Comma-separated appending logic
                                    const parts = inputEl.value.split(",");
                                    parts.pop(); 
                                    parts.push(this.innerText);
                                    inputEl.value = parts.join(", ") + (parts.length > 0 ? ", " : "");
                                } else {
                                    inputEl.value = this.innerText;
                                }
                                dropdownEl.style.display = "none";
                                inputEl.focus(); // Keep the cursor in the box
                                e.stopPropagation();
                            });
                            dropdownEl.appendChild(itemDiv);
                        });
                        dropdownEl.style.display = "block";
                    }
                } catch (error) {
                    dropdownEl.style.display = "none";
                } finally {
                    if (loaderEl) loaderEl.style.display = "none";
                }
            }

            inputEl.addEventListener("input", function() {
                clearTimeout(timeoutId);
                let query = this.value;
                if (isMulti) {
                    const parts = query.split(",");
                    query = parts[parts.length - 1].trim(); // Only search the text after the last comma
                } else {
                    query = query.trim();
                }
                timeoutId = setTimeout(() => fetchSuggestions(query), 150); 
            });

            // Trigger fetch immediately when the user clicks the box
            inputEl.addEventListener("focus", function() {
                let query = this.value;
                if (isMulti) {
                    const parts = query.split(",");
                    query = parts[parts.length - 1].trim();
                } else {
                    query = query.trim();
                }
                fetchSuggestions(query);
            });

            document.addEventListener("click", function (e) {
                if (e.target !== inputEl && e.target !== dropdownEl) {
                    dropdownEl.style.display = "none";
                }
            });
        }

        // Initialize with isMulti set to TRUE only for the Person box
        setupApiAutocomplete("personInput", "personDropdown", "/api/suggest_person", true);
        setupApiAutocomplete("filenameInput", "filenameDropdown", "/api/suggest?column=original_name", false);
        setupApiAutocomplete("cameraInput", "cameraDropdown", "/api/suggest?column=camera_model", false);
        setupApiAutocomplete("locationInput", "locationDropdown", "/api/suggest?column=location_name", false);

        const galleryData = [
            {% for item in results %}
            { type: "{{ item.file_type }}", src: "/file?path={{ item.current_path | urlencode }}" }{% if not loop.last %},{% endif %}
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
                modalImg.src = item.src; modalImg.style.display = 'block';
            } else if (item.type === 'video') {
                modalVid.src = item.src; modalVid.style.display = 'block'; modalVid.play();
            }
            counter.innerText = `${currentIndex + 1} / ${galleryData.length}`;
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }

        function closeLightbox() {
            modal.style.display = 'none'; modalVid.pause(); modalVid.src = ''; modalImg.src = '';
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
    </script>
</body>
</html>
"""

# ==========================================
# TEMPLATE 2: THE PEOPLE MANAGER
# ==========================================
PEOPLE_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>People & Faces</title>
    <style>
        body { font-family: system-ui, sans-serif; background: #121212; color: #e0e0e0; padding: 20px; margin: 0; }
        
        .top-nav { display: flex; gap: 20px; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333; }
        .top-nav a { color: #888; text-decoration: none; font-size: 1.2em; font-weight: bold; transition: color 0.2s; }
        .top-nav a.active { color: #00bfff; }
        .top-nav a:hover { color: #fff; }

        .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab-btn { padding: 10px 20px; background: #2a2a2a; color: #888; border: 1px solid #444; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 1em; }
        .tab-btn.active { background: #007bff; color: #fff; border-color: #007bff; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 20px; }
        
        .person-card { background: #1e1e1e; border-radius: 8px; overflow: hidden; border: 1px solid #333; text-align: center; padding-bottom: 15px; }
        .person-card img { width: 100%; height: 200px; object-fit: cover; }
        .person-card h3 { margin: 10px 0 5px 0; font-size: 1.1em; color: #fff; }
        .person-card p { margin: 0 0 10px 0; font-size: 0.85em; color: #888; }
        
        .name-input-group { display: flex; padding: 0 10px; gap: 5px; }
        .name-input-group input { flex-grow: 1; padding: 8px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 4px; outline: none; }
        .name-input-group button { padding: 8px 12px; background: #28a745; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .name-input-group button:hover { background: #218838; }

        .gallery-link { display: block; text-decoration: none; transition: transform 0.1s; }
        .gallery-link:hover { transform: scale(1.02); }
    </style>
</head>
<body>

    <div class="top-nav">
        <a href="/">📷 Media Archive</a>
        <a href="/people" class="active">👥 People & Faces</a>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('unnamed')">Inbox: Who is this?</button>
        <button class="tab-btn" onclick="switchTab('named')">Gallery: Named People</button>
    </div>

    <div id="unnamed-tab" class="grid">
        {% for c in unnamed %}
        <div class="person-card" id="cluster-{{ c.cluster_id }}">
            <a href="/?person=cluster:{{ c.cluster_id }}" target="_blank" title="Click to view all photos in this cluster">
                <img src="/thumbnail?path={{ c.sample_path | urlencode }}&type={{ c.file_type }}">
            </a>
            <h3>Cluster #{{ c.cluster_id }}</h3>
            <p>{{ c.face_count }} Photos</p>
            <div class="name-input-group">
                <input type="text" id="input-{{ c.cluster_id }}" placeholder="Type name..." onkeypress="handleEnter(event, {{ c.cluster_id }})">
                <button onclick="submitName({{ c.cluster_id }})">Save</button>
            </div>
        </div>
        {% else %}
            <p style="color: #888; grid-column: 1 / -1;">No unnamed people found! Either your archive is fully tagged, or the background scanner is still running.</p>
        {% endfor %}
    </div>

    <div id="named-tab" class="grid" style="display: none;">
        {% for p in named %}
        <a href="/?person={{ p.person_name | urlencode }}" class="gallery-link">
            <div class="person-card">
                <img src="/thumbnail?path={{ p.sample_path | urlencode }}&type={{ p.file_type }}" style="border-radius: 50%; width: 150px; height: 150px; margin: 20px auto 10px auto;">
                <h3>{{ p.person_name }}</h3>
                <p>{{ p.face_count }} Photos</p>
            </div>
        </a>
        {% else %}
            <p style="color: #888; grid-column: 1 / -1;">You haven't named anyone yet. Go to the Inbox tab to start tagging!</p>
        {% endfor %}
    </div>

    <script>
        function switchTab(tabName) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            document.getElementById('unnamed-tab').style.display = tabName === 'unnamed' ? 'grid' : 'none';
            document.getElementById('named-tab').style.display = tabName === 'named' ? 'grid' : 'none';
        }

        function handleEnter(event, clusterId) {
            if (event.key === 'Enter') submitName(clusterId);
        }

        async function submitName(clusterId) {
            const inputEl = document.getElementById(`input-${clusterId}`);
            const name = inputEl.value.trim();
            if (!name) return;

            try {
                const response = await fetch('/api/name_cluster', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cluster_id: clusterId, person_name: name })
                });
                
                if (response.ok) {
                    document.getElementById(`cluster-${clusterId}`).style.display = 'none';
                } else {
                    alert('Failed to save name.');
                }
            } catch (error) {
                console.error(error);
            }
        }
    </script>
</body>
</html>
"""

@app.template_filter('urlencode')
def urlencode_filter(s):
    if type(s) == 'Markup': s = s.unescape()
    s = s.encode('utf8')
    return urllib.parse.quote_plus(s)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- API ROUTES FOR MAIN ARCHIVE ---
@app.route("/api/suggest")
def api_suggest():
    column = request.args.get("column")
    query_str = request.args.get("q", "")
    valid_columns = {"original_name", "camera_model", "location_name"}
    if column not in valid_columns: return jsonify([])
    
    conn = get_db_connection()
    # Now returns top 50 matches so the click-to-open dropdown is fully populated
    if query_str:
        results = conn.execute(f"SELECT DISTINCT {column} FROM media WHERE {column} LIKE ? ORDER BY {column} LIMIT 50", (f"%{query_str}%",)).fetchall()
    else:
        results = conn.execute(f"SELECT DISTINCT {column} FROM media WHERE {column} IS NOT NULL ORDER BY {column} LIMIT 50").fetchall()
    conn.close()
    
    return jsonify([row[0] for row in results if row[0]])

@app.route("/api/suggest_person")
def api_suggest_person():
    query_str = request.args.get("q", "")
    conn = get_db_connection()
    
    # Returns top 50 named people
    if query_str:
        results = conn.execute("SELECT DISTINCT person_name FROM faces WHERE person_name LIKE ? ORDER BY person_name LIMIT 50", (f"%{query_str}%",)).fetchall()
    else:
        results = conn.execute("SELECT DISTINCT person_name FROM faces WHERE person_name IS NOT NULL ORDER BY person_name LIMIT 50").fetchall()
    conn.close()
    
    return jsonify([row[0] for row in results if row[0]])

@app.route("/thumbnail")
def serve_thumbnail():
    file_path = request.args.get("path")
    file_type = request.args.get("type", "image")
    if not file_path or not os.path.exists(file_path): return "Not found", 404
        
    path_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
    cache_path = THUMB_DIR / f"{path_hash}.jpg"
    
    if cache_path.exists(): return send_file(cache_path)
    
    if file_type == "image":
        try:
            with Image.open(file_path) as img:
                img = ImageOps.exif_transpose(img) 
                if img.mode != 'RGB': img = img.convert('RGB')
                img.thumbnail((400, 400))
                img.save(cache_path, "JPEG", quality=75)
            return send_file(cache_path)
        except Exception: return send_file(file_path)
    elif file_type == "video":
        try:
            subprocess.run(["ffmpeg", "-y", "-i", file_path, "-ss", "00:00:00.100", "-vframes", "1", "-vf", "scale=400:-1", str(cache_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return send_file(cache_path)
        except Exception: return send_file(file_path)

@app.route("/file")
def serve_file():
    file_path = request.args.get("path")
    if file_path and os.path.exists(file_path): return send_file(file_path)
    return "File not found", 404

# --- PEOPLE UI & API ROUTES ---
@app.route("/people")
def people_manager():
    conn = get_db_connection()
    unnamed_query = """
        SELECT f.cluster_id, COUNT(f.id) as face_count, m.current_path as sample_path, m.file_type 
        FROM faces f JOIN media m ON f.media_id = m.id 
        WHERE f.person_name IS NULL AND f.cluster_id != -1 
        GROUP BY f.cluster_id ORDER BY face_count DESC
    """
    unnamed = conn.execute(unnamed_query).fetchall()
    named_query = """
        SELECT f.person_name, COUNT(f.id) as face_count, MIN(m.current_path) as sample_path, m.file_type 
        FROM faces f JOIN media m ON f.media_id = m.id 
        WHERE f.person_name IS NOT NULL 
        GROUP BY f.person_name ORDER BY f.person_name ASC
    """
    named = conn.execute(named_query).fetchall()
    conn.close()
    return render_template_string(PEOPLE_HTML_TEMPLATE, unnamed=unnamed, named=named)

@app.route("/api/name_cluster", methods=["POST"])
def name_cluster():
    data = request.json
    cluster_id = data.get("cluster_id")
    person_name = data.get("person_name")
    if cluster_id is None or not person_name: return jsonify({"error": "Invalid data"}), 400
        
    conn = get_db_connection()
    conn.execute("UPDATE faces SET person_name = ? WHERE cluster_id = ?", (person_name.strip(), cluster_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

# --- MAIN ARCHIVE ROUTE ---
@app.route("/")
def index():
    try: page = int(request.args.get("page", 1))
    except ValueError: page = 1

    source = request.args.get("source", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    camera = request.args.get("camera", "")
    location = request.args.get("location", "")
    name = request.args.get("name", "")
    file_type = request.args.get("file_type", "")
    has_gps = request.args.get("has_gps", "")
    flash = request.args.get("flash", "")
    person = request.args.get("person", "") 
    
    sort_param = request.args.get("sort", "date_desc")
    sort_mapping = {
        "date_desc": "date_taken DESC", "date_asc": "date_taken ASC",
        "size_desc": "file_size_kb DESC", "size_asc": "file_size_kb ASC"
    }
    order_by_clause = sort_mapping.get(sort_param, "date_taken DESC")

    conditions = ""
    params = []
    
    # --- UPGRADED: Partial and Multi-Person Logic ---
    if person:
        if person.startswith("cluster:"):
            cluster_id = person.split(":")[1]
            conditions += " AND media.id IN (SELECT media_id FROM faces WHERE cluster_id = ?)"
            params.append(int(cluster_id))
        else:
            # Allows comma-separated multi-person searching!
            people_list = [p.strip() for p in person.split(",") if p.strip()]
            for p in people_list:
                conditions += " AND media.id IN (SELECT media_id FROM faces WHERE person_name LIKE ?)"
                params.append(f"%{p}%")

    if source: conditions += " AND source = ?"; params.append(source)
    if camera: conditions += " AND camera_model LIKE ?"; params.append(f"%{camera}%")
    if location: conditions += " AND location_name LIKE ?"; params.append(f"%{location}%")
    if start_date: conditions += " AND date_taken >= ?"; params.append(start_date + " 00:00:00")
    if end_date: conditions += " AND date_taken <= ?"; params.append(end_date + " 23:59:59")
    if name: conditions += " AND original_name LIKE ?"; params.append(f"%{name}%")
    if file_type: conditions += " AND file_type = ?"; params.append(file_type)
    if has_gps == "1": conditions += " AND latitude IS NOT NULL"
    if flash == "1": conditions += " AND flash_fired = 1"

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
        SELECT original_name, current_path, file_type, source, date_taken, camera_model, file_size_kb, location_name 
        FROM media WHERE 1=1 {conditions} ORDER BY {order_by_clause} LIMIT {per_page} OFFSET ?
    """
    params.append(offset)
    results = conn.execute(data_query, params).fetchall()
    conn.close()
    
    return render_template_string(HTML_TEMPLATE, results=results, page=page, total_pages=total_pages, total_count=total_count)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
