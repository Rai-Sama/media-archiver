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
        
        .top-nav { display: flex; gap: 20px; margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333; justify-content: space-between; align-items: center;}
        .nav-links { display: flex; gap: 20px; }
        .nav-links a { color: #888; text-decoration: none; font-size: 1.2em; font-weight: bold; transition: color 0.2s; }
        .nav-links a.active { color: #00bfff; }
        .nav-links a:hover { color: #fff; }

        .batch-toggle-btn { padding: 8px 15px; background: #2a2a2a; color: #fff; border: 1px solid #444; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.2s; }
        .batch-toggle-btn.active { background: #00bfff; border-color: #00bfff; color: #000; }

        .header-container { background: #1e1e1e; padding: 20px; border-radius: 8px; margin-bottom: 25px; border: 1px solid #333; }
        .search-form { display: flex; flex-direction: column; gap: 15px; }
        .filter-row { display: flex; gap: 15px; flex-wrap: wrap; align-items: flex-end; }
        .filter-label { font-size: 0.85em; color: #aaa; margin-bottom: 4px; display: block; text-transform: uppercase; letter-spacing: 0.5px; }
        
        input[type="text"], input[type="date"], select { padding: 10px; background: #2a2a2a; color: white; border: 1px solid #444; border-radius: 6px; outline: none; min-width: 150px; box-sizing: border-box; }
        input:focus, select:focus { border-color: #007bff; }
        input::-webkit-calendar-picker-indicator { opacity: 1; cursor: pointer; filter: invert(0.8); }
        
        button { cursor: pointer; background: #007bff; color: white; padding: 10px 20px; font-weight: bold; border: none; border-radius: 6px; height: 40px; box-sizing: border-box;}
        button:hover:not(:disabled) { background: #0056b3; }
        .clear-btn { padding: 10px 15px; background: #444; color: white; text-decoration: none; border-radius: 6px; font-size: 0.9em; height: 40px; box-sizing: border-box; display: flex; align-items: center; justify-content: center;}
        
        .input-group { display: flex; flex-direction: column; }
        .autocomplete-wrapper { position: relative; }
        .autocomplete-dropdown { position: absolute; top: 100%; left: 0; z-index: 999; width: max-content; min-width: 100%; max-width: 400px; max-height: 250px; overflow-y: auto; background-color: #2a2a2a; border: 1px solid #444; border-radius: 4px; box-shadow: 0 8px 16px rgba(0,0,0,0.8); display: none; margin-top: 4px; }
        .autocomplete-dropdown.drop-up { top: auto; bottom: 100%; margin-top: 0; margin-bottom: 4px; }
        .autocomplete-item { padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #333; word-break: break-all; color: #fff; font-size: 0.9em;}
        .autocomplete-item:hover { background-color: #007bff; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 15px; }
        .card { background: #1e1e1e; border-radius: 8px; overflow: hidden; border: 1px solid #333; transition: transform 0.1s; position: relative; }
        .card:hover { border-color: #555; }
        
        .card.selected { border: 3px solid #00bfff; transform: scale(0.98); }
        .card.selected::after { content: '✓'; position: absolute; top: 10px; right: 10px; background: #00bfff; color: #000; width: 25px; height: 25px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; pointer-events: none; }

        .media-container { height: 200px; width: 100%; background: #0b0b0b; display: flex; align-items: center; justify-content: center; overflow: hidden; cursor: pointer; position: relative; }
        .media-container img { width: 100%; height: 100%; object-fit: cover; pointer-events: none; transition: transform 0.2s; }
        .media-container:hover img { transform: scale(1.03); opacity: 0.8; }
        .play-icon { position: absolute; font-size: 3em; color: rgba(255, 255, 255, 0.7); pointer-events: none; }

        .info { padding: 12px; font-size: 0.85em; color: #ccc; line-height: 1.5; }
        .badge { display: inline-block; padding: 2px 6px; background: #333; border-radius: 4px; font-size: 0.8em; margin-bottom: 6px; font-weight: bold; }

        .pagination { display: flex; justify-content: center; align-items: center; gap: 15px; margin-top: 30px; padding-bottom: 80px; }
        .page-btn { padding: 10px 20px; background: #2a2a2a; color: #fff; border: 1px solid #444; border-radius: 6px; cursor: pointer; font-weight: bold; }
        .page-info { color: #aaa; font-size: 0.9em; font-family: monospace; }

        /* Lightbox */
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.95); justify-content: center; align-items: center; backdrop-filter: blur(5px); }
        .modal-content-wrapper { position: relative; max-width: 90%; max-height: 85vh; display: inline-block; margin-bottom: 50px; overflow: hidden; }
        .modal-content { max-width: 100%; max-height: 85vh; object-fit: contain; border-radius: 4px; box-shadow: 0 4px 25px rgba(0,0,0,0.8); display: none; transform-origin: 0 0; }
        .modal-close { position: absolute; top: 20px; right: 30px; color: #fff; font-size: 40px; font-weight: bold; cursor: pointer; user-select: none; z-index: 1001; }
        .nav-btn { position: absolute; top: 50%; transform: translateY(-50%); color: #fff; font-size: 50px; cursor: pointer; padding: 20px; z-index: 1001; transition: 0.2s; user-select: none; }
        .nav-btn:hover { color: #00bfff; }
        
        .floating-tag-bar { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 1002; display: flex; align-items: center; gap: 15px; background: rgba(30, 30, 30, 0.95); padding: 15px 20px; border-radius: 8px; border: 1px solid #555; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }
        .floating-tag-bar input[type="text"] { width: 200px; background: #121212; border: 1px solid #555; color: white; padding: 10px; border-radius: 4px; }
        .floating-tag-bar label { color: #ccc; font-size: 0.85em; display: flex; align-items: center; gap: 6px; cursor: pointer; }
        .floating-tag-bar button { height: auto; padding: 10px 20px; font-size: 0.9em; background: #28a745; }
        
        .inspect-btn { background: #6f42c1 !important; margin-right: 15px; }
        .inspect-btn.active { background: #d63384 !important; }

        /* Bounding Boxes & Custom Drawing */
        #faceOverlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1001; display: none; }
        .face-box { position: absolute; border: 3px solid rgba(0, 191, 255, 0.8); border-radius: 4px; background: rgba(0, 191, 255, 0.1); cursor: pointer; pointer-events: auto; transition: 0.2s; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; }
        .face-box:hover { border-color: #00bfff; background: rgba(0, 191, 255, 0.3); z-index: 10; }
        .face-box.drawing { border: 3px dashed #d63384; background: rgba(214, 51, 132, 0.2); pointer-events: none; transition: none; }
        .face-box .box-label { background: rgba(0, 0, 0, 0.8); color: white; font-size: 12px; padding: 2px 6px; border-radius: 4px; margin-bottom: -25px; white-space: nowrap; }
        .face-box.tagged { border-color: rgba(40, 167, 69, 0.8); background: rgba(40, 167, 69, 0.1); }
        .face-box.tagged:hover { border-color: #28a745; background: rgba(40, 167, 69, 0.3); }

        /* Delete Button for Boxes */
        .delete-box-btn { position: absolute; top: -12px; right: -12px; background: #dc3545; color: white; border-radius: 50%; width: 24px; height: 24px; text-align: center; line-height: 22px; font-weight: bold; cursor: pointer; font-size: 14px; display: none; z-index: 11; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
        .face-box:hover .delete-box-btn { display: block; }
        .delete-box-btn:hover { background: #c82333; transform: scale(1.1); }

        #boxTagger { position: absolute; z-index: 1003; background: #1e1e1e; border: 1px solid #444; border-radius: 6px; padding: 10px; display: none; box-shadow: 0 4px 15px rgba(0,0,0,0.8); }
        #boxTagger input { background: #121212; border: 1px solid #555; color: white; padding: 6px 10px; border-radius: 4px; width: 150px; outline: none;}
        #boxTagger button { background: #007bff; padding: 6px 12px; height: auto; margin-top: 8px; width: 100%; border: none; border-radius: 4px; cursor: pointer; color: #fff; font-weight: bold;}
    </style>
</head>
<body>

    <div class="top-nav">
        <div class="nav-links">
            <a href="/" class="active">📷 Media Archive</a>
            <a href="/people">👥 People & Faces</a>
        </div>
        <button id="batchToggleBtn" class="batch-toggle-btn" onclick="toggleBatchMode()">Batch Tag Mode</button>
    </div>

    <div class="header-container">
        <form class="search-form" method="GET" action="/">
            <div class="filter-row">
                <div class="input-group">
                    <span class="filter-label">Person</span>
                    <div class="autocomplete-wrapper">
                        <input type="text" id="personInput" name="person" placeholder="e.g., John, Jane" value="{{ request.args.get('person', '') }}" autocomplete="off" style="width: 180px; border-color: #00bfff;">
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
                        <div id="cameraDropdown" class="autocomplete-dropdown"></div>
                    </div>
                </div>
            </div>
            
            <div class="filter-row">
                <div class="input-group">
                    <span class="filter-label">Location</span>
                    <div class="autocomplete-wrapper">
                        <input type="text" id="locationInput" name="location" placeholder="City or State..." value="{{ request.args.get('location', '') }}" autocomplete="off" style="width: 180px;">
                        <div id="locationDropdown" class="autocomplete-dropdown"></div>
                    </div>
                </div>

                <div class="input-group">
                    <span class="filter-label">File Name</span>
                    <div class="autocomplete-wrapper">
                        <input type="text" id="filenameInput" name="name" placeholder="Exact snippet..." value="{{ request.args.get('name', '') }}" autocomplete="off" style="min-width: 180px;">
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
        <div class="card" id="card-{{ loop.index0 }}" onclick="handleMediaClick({{ loop.index0 }}, '{{ item.current_path | urlencode }}')">
            <div class="media-container">
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
                {% if item.people %}
                    {% for person in item.people.split(',') %}
                        <div class="badge" style="background:#1e4b35; color:#a3e4c4;">👤 {{ person }}</div>
                    {% endfor %}
                {% endif %}
                
                {% if item.camera_model %}<div class="badge" style="background:#2b4b6f;">{{ item.camera_model[:15] }}</div>{% endif %}
                {% if item.location_name %}<div class="badge" style="background:#8b0000; color:#ffcccc;">📍 {{ item.location_name }}</div>{% endif %}
                <br>
                <strong style="color: #fff; word-break: break-all;">{{ item.original_name[:30] }}</strong><br>
                <span style="color: #999;">{{ item.date_taken if item.date_taken else 'Unknown Date' }}</span>
            </div>
        </div>
        {% endfor %}
    </div>

    {% if total_pages > 0 %}
    <div class="pagination">
        <button class="page-btn" onclick="changePage({{ page - 1 }})" {% if page <= 1 %}disabled{% endif %}>&#10094; Prev</button>
        <span class="page-info">Page {{ page }} of {{ total_pages }}</span>
        <button class="page-btn" onclick="changePage({{ page + 1 }})" {% if page >= total_pages %}disabled{% endif %}>Next &#10095;</button>
    </div>
    {% endif %}

    <div id="lightboxModal" class="modal" onclick="closeLightbox(event)">
        <span class="modal-close" onclick="closeLightbox(event)">&times;</span>
        <div class="nav-btn prev-btn" style="left:10px;" onclick="navigate(-1, event)">&#10094;</div>
        
        <div class="modal-content-wrapper">
            <img class="modal-content" id="modalImg" draggable="false" onclick="event.stopPropagation();">
            <video class="modal-content" id="modalVid" controls onclick="event.stopPropagation();"></video>
            <div id="faceOverlay"></div>
        </div>
        
        <div class="nav-btn next-btn" style="right:10px;" onclick="navigate(1, event)">&#10095;</div>
        
        <div class="floating-tag-bar" onclick="event.stopPropagation();">
            <button id="inspectToggleBtn" class="inspect-btn" onclick="toggleInspector()">👁️ Inspect Faces</button>
            <div class="autocomplete-wrapper" style="overflow: visible;">
                <input type="text" id="lightboxTagInput" placeholder="Tag whole photo..." autocomplete="off">
                <div id="lightboxTagDropdown" class="autocomplete-dropdown drop-up"></div>
            </div>
            <label>
                <input type="checkbox" id="lightboxExcludeCb"> Exclude from ML
            </label>
            <button id="lightboxTagBtn" onclick="submitTag(false)">Add Tag</button>
        </div>

        <div id="boxTagger" onclick="event.stopPropagation();">
            <div class="autocomplete-wrapper" style="overflow: visible;">
                <input type="text" id="boxTagInput" placeholder="Name this face..." autocomplete="off">
                <div id="boxTagDropdown" class="autocomplete-dropdown drop-up"></div>
            </div>
            <label style="display:block; margin-top:8px; font-size:0.8em; color:#ccc; cursor:pointer;">
                <input type="checkbox" id="boxExcludeCb"> Exclude from ML
            </label>
            <button id="boxTagBtn" onclick="submitBoxTag()">Save Face</button>
            <input type="hidden" id="activeFaceId">
        </div>
    </div>

    <div id="batchTagBar" class="floating-tag-bar" style="display: none;">
        <span id="batchCount" style="color: #00bfff; font-weight: bold; width: 60px;">0 Selected</span>
        <div class="autocomplete-wrapper" style="overflow: visible;">
            <input type="text" id="batchTagInput" placeholder="Tag selected photos..." autocomplete="off">
            <div id="batchTagDropdown" class="autocomplete-dropdown drop-up"></div>
        </div>
        <label><input type="checkbox" id="batchExcludeCb"> Exclude from ML</label>
        <button id="batchTagBtn" onclick="submitTag(true)">Tag Selected</button>
    </div>

    <script>
        function changePage(newPage) {
            const url = new URL(window.location.href);
            url.searchParams.set('page', newPage);
            window.location.href = url.toString();
        }

        const galleryData = [
            {% for item in results %}
            { type: "{{ item.file_type }}", src: "/file?path={{ item.current_path | urlencode }}" }{% if not loop.last %},{% endif %}
            {% endfor %}
        ];
        
        let isBatchMode = false;
        let selectedPaths = new Set();
        let currentIndex = 0;
        let inspectorActive = false;

        function toggleBatchMode() {
            isBatchMode = !isBatchMode;
            const btn = document.getElementById('batchToggleBtn');
            const batchBar = document.getElementById('batchTagBar');
            if (isBatchMode) {
                btn.classList.add('active'); batchBar.style.display = 'flex'; btn.innerText = 'Cancel Batch Mode';
            } else {
                btn.classList.remove('active'); batchBar.style.display = 'none'; btn.innerText = 'Batch Tag Mode';
                selectedPaths.clear();
                document.querySelectorAll('.card.selected').forEach(c => c.classList.remove('selected'));
                document.getElementById('batchCount').innerText = `0 Selected`;
            }
        }

        function handleMediaClick(index, encodedPath) {
            if (isBatchMode) {
                const card = document.getElementById(`card-${index}`);
                const path = decodeURIComponent(encodedPath);
                if (selectedPaths.has(path)) { selectedPaths.delete(path); card.classList.remove('selected'); } 
                else { selectedPaths.add(path); card.classList.add('selected'); }
                document.getElementById('batchCount').innerText = `${selectedPaths.size} Selected`;
            } else { openLightbox(index); }
        }

        const modal = document.getElementById('lightboxModal');
        const modalImg = document.getElementById('modalImg');
        const modalVid = document.getElementById('modalVid');
        const faceOverlay = document.getElementById('faceOverlay');
        const boxTagger = document.getElementById('boxTagger');

        // --- ZOOM & PAN VARIABLES ---
        let imgScale = 1, imgPointX = 0, imgPointY = 0, panningImg = false, startImgX = 0, startImgY = 0;

        function setImgTransform() {
            modalImg.style.transform = `translate(${imgPointX}px, ${imgPointY}px) scale(${imgScale})`;
            modalImg.style.cursor = imgScale > 1 ? (panningImg ? 'grabbing' : 'grab') : 'default';
        }

        modalImg.addEventListener('wheel', (e) => {
            if (inspectorActive) return; 
            e.preventDefault();
            const xs = (e.clientX - imgPointX) / imgScale;
            const ys = (e.clientY - imgPointY) / imgScale;
            const delta = (e.wheelDelta ? e.wheelDelta : -e.deltaY);
            
            (delta > 0) ? (imgScale *= 1.2) : (imgScale /= 1.2);
            imgScale = Math.max(1, Math.min(imgScale, 12)); 
            
            if (imgScale === 1) { imgPointX = 0; imgPointY = 0; } 
            else { imgPointX = e.clientX - xs * imgScale; imgPointY = e.clientY - ys * imgScale; }
            setImgTransform();
        });

        modalImg.addEventListener('mousedown', (e) => {
            if (inspectorActive || imgScale === 1) return;
            e.preventDefault();
            startImgX = e.clientX - imgPointX; startImgY = e.clientY - imgPointY;
            panningImg = true; setImgTransform();
        });

        window.addEventListener('mouseup', () => { if(panningImg) { panningImg = false; setImgTransform(); } });

        window.addEventListener('mousemove', (e) => {
            if (!panningImg || inspectorActive) return;
            e.preventDefault();
            imgPointX = e.clientX - startImgX; imgPointY = e.clientY - startImgY;
            setImgTransform();
        });

        function openLightbox(index) {
            if (index < 0 || index >= galleryData.length || galleryData[index].type === 'document') return;
            currentIndex = index;
            const item = galleryData[currentIndex];
            
            imgScale = 1; imgPointX = 0; imgPointY = 0; setImgTransform();
            
            modalImg.style.display = 'none'; modalVid.style.display = 'none'; modalVid.pause();
            inspectorActive = false; document.getElementById('inspectToggleBtn').classList.remove('active');
            faceOverlay.style.display = 'none'; boxTagger.style.display = 'none';
            faceOverlay.style.pointerEvents = 'none';
            
            if (item.type === 'image') { modalImg.src = item.src; modalImg.style.display = 'block'; } 
            else if (item.type === 'video') { modalVid.src = item.src; modalVid.style.display = 'block'; modalVid.play(); }
            
            modal.style.display = 'flex'; document.body.style.overflow = 'hidden';
            document.getElementById('lightboxTagInput').value = '';
        }

        function closeLightbox(event) {
            if(event && event.target !== modal && event.target !== document.querySelector('.modal-close')) return;
            modal.style.display = 'none'; modalVid.pause(); modalVid.src = ''; modalImg.src = '';
            document.body.style.overflow = 'auto'; document.getElementById('lightboxTagDropdown').style.display = 'none';
            boxTagger.style.display = 'none';
        }

        function navigate(direction, event) {
            if (event) event.stopPropagation();
            let nextIndex = currentIndex + direction;
            while (nextIndex >= 0 && nextIndex < galleryData.length && galleryData[nextIndex].type === 'document') nextIndex += direction;
            if (nextIndex >= galleryData.length) nextIndex = 0;
            if (nextIndex < 0) nextIndex = galleryData.length - 1;
            openLightbox(nextIndex);
        }

        // --- FACE INSPECTOR & CUSTOM DRAWING ---
        let isDrawing = false;
        let drawStartX = 0;
        let drawStartY = 0;
        let currentCustomBox = null;
        let customBoxData = null; 

        faceOverlay.addEventListener('mousedown', (e) => {
            if(e.target !== faceOverlay) return; 
            isDrawing = true;
            drawStartX = e.offsetX;
            drawStartY = e.offsetY;
            currentCustomBox = document.createElement('div');
            currentCustomBox.className = 'face-box drawing';
            currentCustomBox.style.left = `${(drawStartX / faceOverlay.clientWidth) * 100}%`;
            currentCustomBox.style.top = `${(drawStartY / faceOverlay.clientHeight) * 100}%`;
            faceOverlay.appendChild(currentCustomBox);
            boxTagger.style.display = 'none';
        });

        faceOverlay.addEventListener('mousemove', (e) => {
            if(!isDrawing || !currentCustomBox) return;
            const currentX = e.offsetX;
            const currentY = e.offsetY;
            const left = Math.min(drawStartX, currentX);
            const top = Math.min(drawStartY, currentY);
            const width = Math.abs(currentX - drawStartX);
            const height = Math.abs(currentY - drawStartY);

            currentCustomBox.style.left = `${(left / faceOverlay.clientWidth) * 100}%`;
            currentCustomBox.style.top = `${(top / faceOverlay.clientHeight) * 100}%`;
            currentCustomBox.style.width = `${(width / faceOverlay.clientWidth) * 100}%`;
            currentCustomBox.style.height = `${(height / faceOverlay.clientHeight) * 100}%`;
        });

        faceOverlay.addEventListener('mouseup', (e) => {
            if(!isDrawing || !currentCustomBox) return;
            isDrawing = false;
            
            if(currentCustomBox.offsetWidth < 15 || currentCustomBox.offsetHeight < 15) {
                currentCustomBox.remove();
                return;
            }

            const leftPct = parseFloat(currentCustomBox.style.left);
            const topPct = parseFloat(currentCustomBox.style.top);
            const widthPct = parseFloat(currentCustomBox.style.width);
            const heightPct = parseFloat(currentCustomBox.style.height);

            customBoxData = {
                top_pct: topPct,
                right_pct: leftPct + widthPct,
                bottom_pct: topPct + heightPct,
                left_pct: leftPct
            };

            openBoxTagger(null, '', e.clientX, e.clientY);
        });

        async function toggleInspector() {
            inspectorActive = !inspectorActive;
            const btn = document.getElementById('inspectToggleBtn');
            boxTagger.style.display = 'none';
            if (!inspectorActive) { 
                btn.classList.remove('active'); 
                faceOverlay.style.display = 'none'; 
                faceOverlay.style.pointerEvents = 'none';
                return; 
            }
            
            imgScale = 1; imgPointX = 0; imgPointY = 0; setImgTransform();
            
            btn.classList.add('active'); 
            faceOverlay.style.display = 'block'; 
            faceOverlay.style.pointerEvents = 'auto'; 
            faceOverlay.style.cursor = 'crosshair';
            
            faceOverlay.innerHTML = '<div style="position:absolute; top:20px; left:50%; transform:translateX(-50%); background:rgba(0,191,255,0.9); color:#000; font-weight:bold; padding:8px 15px; border-radius:20px; font-size:14px; pointer-events:none; z-index:1000; box-shadow: 0 4px 10px rgba(0,0,0,0.5);">✏️ Click & Drag to manually select a missing face</div>';

            if(galleryData[currentIndex].type !== 'image') { alert("Inspector supports Images only."); toggleInspector(); return; }

            const urlParams = new URLSearchParams(galleryData[currentIndex].src.split('?')[1]);
            try {
                // FIXED PARSING: The backend returns {"faces": [...], "thumb_w": X, "thumb_h": Y}
                const res = await fetch(`/api/get_faces?path=${encodeURIComponent(urlParams.get('path'))}`);
                const data = await res.json();
                
                const thumbW = data.thumb_w;
                const thumbH = data.thumb_h;

                data.faces.forEach(face => {
                    if(face.box_top === null || face.box_top === undefined) return;
                    
                    // Fixed translation math uses the backend's explicit thumbnail dimensions
                    const topPct = (face.box_top / thumbH) * 100; 
                    const leftPct = (face.box_left / thumbW) * 100;
                    const widthPct = ((face.box_right - face.box_left) / thumbW) * 100; 
                    const heightPct = ((face.box_bottom - face.box_top) / thumbH) * 100;

                    const box = document.createElement('div');
                    box.className = `face-box ${face.person_name ? 'tagged' : ''}`;
                    box.style.top = `${topPct}%`; box.style.left = `${leftPct}%`;
                    box.style.width = `${widthPct}%`; box.style.height = `${heightPct}%`;
                    
                    if(face.person_name) {
                        const label = document.createElement('div'); label.className = 'box-label'; label.innerText = face.person_name; box.appendChild(label);
                    }
                    
                    const deleteBtn = document.createElement('div');
                    deleteBtn.className = 'delete-box-btn';
                    deleteBtn.innerText = '×';
                    deleteBtn.title = 'Remove this face box';
                    deleteBtn.addEventListener('click', async (e) => {
                        e.stopPropagation();
                        const delRes = await fetch('/api/delete_face', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ face_id: face.id })
                        });
                        if(delRes.ok) box.remove();
                    });
                    box.appendChild(deleteBtn);

                    box.addEventListener('click', (e) => { e.stopPropagation(); openBoxTagger(face.id, face.person_name, e.clientX, e.clientY); });
                    faceOverlay.appendChild(box);
                });
            } catch(e) { console.error("Error fetching faces", e); }
        }

        function openBoxTagger(faceId, existingName, clickX, clickY) {
            document.getElementById('activeFaceId').value = faceId || '';
            document.getElementById('boxTagInput').value = existingName || '';
            document.getElementById('boxExcludeCb').checked = false; 
            
            boxTagger.style.left = `${clickX}px`; boxTagger.style.top = `${clickY + 20}px`;
            boxTagger.style.display = 'block'; document.getElementById('boxTagInput').focus();
        }

        async function submitBoxTag() {
            const name = document.getElementById('boxTagInput').value.trim();
            const faceId = document.getElementById('activeFaceId').value;
            const excludeMl = document.getElementById('boxExcludeCb').checked;
            
            if(!name) return;
            const btn = document.getElementById('boxTagBtn'); btn.innerText = '...';

            try {
                if (faceId) {
                    const res = await fetch('/api/tag_specific_face', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ face_id: faceId, person_name: name, exclude_from_ml: excludeMl })
                    });
                    if(res.ok) { boxTagger.style.display = 'none'; btn.innerText = 'Save Face'; inspectorActive = false; toggleInspector(); }
                } else if (customBoxData) {
                    const urlParams = new URLSearchParams(galleryData[currentIndex].src.split('?')[1]);
                    const filePath = decodeURIComponent(urlParams.get('path'));
                    
                    const res = await fetch('/api/add_custom_face', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: filePath, person_name: name, box: customBoxData, exclude_from_ml: excludeMl })
                    });
                    if(res.ok) { boxTagger.style.display = 'none'; btn.innerText = 'Save Face'; customBoxData = null; inspectorActive = false; toggleInspector(); }
                }
            } catch(e) { btn.innerText = 'Error'; }
        }

        async function submitTag(isBatch) {
            let name, excludeMl, paths, btnEl;
            if (isBatch) {
                name = document.getElementById('batchTagInput').value.trim();
                excludeMl = document.getElementById('batchExcludeCb').checked;
                paths = Array.from(selectedPaths);
                btnEl = document.getElementById('batchTagBtn');
                if (paths.length === 0) return;
            } else {
                name = document.getElementById('lightboxTagInput').value.trim();
                excludeMl = document.getElementById('lightboxExcludeCb').checked;
                const urlParams = new URLSearchParams(galleryData[currentIndex].src.split('?')[1]);
                paths = [decodeURIComponent(urlParams.get('path'))];
                btnEl = document.getElementById('lightboxTagBtn');
            }
            if (!name) return;
            btnEl.innerText = 'Saving...';
            try {
                const res = await fetch('/api/add_manual_tag', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paths: paths, person_name: name, exclude_from_ml: excludeMl })
                });
                if (res.ok) {
                    btnEl.innerText = 'Saved!'; btnEl.className = 'success';
                    if (isBatch) setTimeout(() => { toggleBatchMode(); btnEl.innerText='Tag Selected'; btnEl.className='';}, 1000);
                    else setTimeout(() => { btnEl.innerText='Add Tag'; btnEl.className=''; }, 2000);
                } else btnEl.innerText = 'Error';
            } catch (error) { btnEl.innerText = 'Error'; }
        }

        function setupApiAutocomplete(inputId, dropdownId, apiEndpoint, isMulti = false) {
            const inputEl = document.getElementById(inputId); const dropdownEl = document.getElementById(dropdownId);
            let timeoutId;
            if (!inputEl || !dropdownEl) return;
            async function fetchSuggestions(query) {
                try {
                    const url = new URL(apiEndpoint, window.location.origin);
                    if (query) url.searchParams.set('q', query);
                    const res = await fetch(url);
                    if (!res.ok) throw new Error();
                    const arr = await res.json();
                    dropdownEl.innerHTML = ""; 
                    if (arr.length === 0) dropdownEl.style.display = "none";
                    else {
                        arr.forEach(txt => {
                            const d = document.createElement("div"); d.className = "autocomplete-item"; d.innerText = txt;
                            d.addEventListener("click", function(e) {
                                if (isMulti) { const p = inputEl.value.split(","); p.pop(); p.push(txt); inputEl.value = p.join(", ") + (p.length > 0 ? ", " : ""); } 
                                else inputEl.value = txt;
                                dropdownEl.style.display = "none"; inputEl.focus(); e.stopPropagation();
                            });
                            dropdownEl.appendChild(d);
                        });
                        dropdownEl.style.display = "block";
                    }
                } catch (e) { dropdownEl.style.display = "none"; }
            }
            inputEl.addEventListener("input", function() {
                clearTimeout(timeoutId); let q = this.value;
                if (isMulti) { const p = q.split(","); q = p[p.length - 1].trim(); } else q = q.trim();
                timeoutId = setTimeout(() => fetchSuggestions(q), 150); 
            });
            inputEl.addEventListener("focus", function() {
                let q = this.value;
                if (isMulti) { const p = q.split(","); q = p[p.length - 1].trim(); } else q = q.trim();
                fetchSuggestions(q);
            });
            document.addEventListener("click", function (e) { if (e.target !== inputEl && e.target !== dropdownEl) dropdownEl.style.display = "none"; });
        }

        setupApiAutocomplete("personInput", "personDropdown", "/api/suggest_person", true);
        setupApiAutocomplete("lightboxTagInput", "lightboxTagDropdown", "/api/suggest_person", false);
        setupApiAutocomplete("batchTagInput", "batchTagDropdown", "/api/suggest_person", false);
        setupApiAutocomplete("boxTagInput", "boxTagDropdown", "/api/suggest_person", false);
        
        setupApiAutocomplete("filenameInput", "filenameDropdown", "/api/suggest?column=original_name", false);
        setupApiAutocomplete("cameraInput", "cameraDropdown", "/api/suggest?column=camera_model", false);
        setupApiAutocomplete("locationInput", "locationDropdown", "/api/suggest?column=location_name", false);

        document.addEventListener('keydown', function(event) {
            if (modal.style.display === 'flex') {
                const isInputActive = document.activeElement && document.activeElement.tagName === 'INPUT';
                
                if (isInputActive) {
                    if (event.key === "Enter") {
                        if(document.activeElement.id === 'boxTagInput') submitBoxTag();
                        else if(document.activeElement.id === 'lightboxTagInput') submitTag(false);
                    }
                    return; 
                }
                
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
        
        .name-input-group { display: flex; padding: 0 10px; gap: 8px; width: 100%; box-sizing: border-box; }
        .name-input-group input { flex-grow: 1; padding: 8px; background: #2a2a2a; border: 1px solid #444; color: #fff; border-radius: 4px; outline: none; min-width: 0; }
        .name-input-group button { flex-shrink: 0; padding: 8px 15px; background: #28a745; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; height: auto; }
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
            <a href="/?person=cluster:{{ c.cluster_id }}" target="_blank"><img src="/thumbnail?path={{ c.sample_path | urlencode }}&type={{ c.file_type }}"></a>
            <h3>Cluster #{{ c.cluster_id }}</h3><p>{{ c.face_count }} Photos</p>
            <div class="name-input-group">
                <input type="text" id="input-{{ c.cluster_id }}" placeholder="Type name..." onkeypress="handleEnter(event, {{ c.cluster_id }})">
                <button onclick="submitName({{ c.cluster_id }})">Save</button>
            </div>
        </div>
        {% endfor %}
    </div>
    <div id="named-tab" class="grid" style="display: none;">
        {% for p in named %}
        <a href="/?person={{ p.person_name | urlencode }}" class="gallery-link">
            <div class="person-card">
                <img src="/thumbnail?path={{ p.sample_path | urlencode }}&type={{ p.file_type }}" style="border-radius: 50%; width: 150px; height: 150px; margin: 20px auto 10px auto;">
                <h3>{{ p.person_name }}</h3><p>{{ p.face_count }} Photos</p>
            </div>
        </a>
        {% endfor %}
    </div>
    <script>
        function switchTab(tabName) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('unnamed-tab').style.display = tabName === 'unnamed' ? 'grid' : 'none';
            document.getElementById('named-tab').style.display = tabName === 'named' ? 'grid' : 'none';
        }
        function handleEnter(event, clusterId) { if (event.key === 'Enter') submitName(clusterId); }
        async function submitName(clusterId) {
            const inputEl = document.getElementById(`input-${clusterId}`);
            if (!inputEl.value.trim()) return;
            const res = await fetch('/api/name_cluster', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ cluster_id: clusterId, person_name: inputEl.value.trim() }) });
            if (res.ok) document.getElementById(`cluster-${clusterId}`).style.display = 'none';
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

# --- API ENDPOINTS ---
@app.route("/api/suggest_person")
def api_suggest_person():
    query_str = request.args.get("q", "")
    conn = get_db_connection()
    if query_str:
        res = conn.execute("SELECT DISTINCT person_name FROM faces WHERE person_name LIKE ? ORDER BY person_name LIMIT 50", (f"%{query_str}%",)).fetchall()
    else:
        res = conn.execute("SELECT DISTINCT person_name FROM faces WHERE person_name IS NOT NULL ORDER BY person_name LIMIT 50").fetchall()
    conn.close()
    return jsonify([r[0] for r in res if r[0]])

@app.route("/api/suggest")
def api_suggest():
    column = request.args.get("column")
    query_str = request.args.get("q", "")
    if column not in {"original_name", "camera_model", "location_name"}: return jsonify([])
    conn = get_db_connection()
    if query_str:
        res = conn.execute(f"SELECT DISTINCT {column} FROM media WHERE {column} LIKE ? ORDER BY {column} LIMIT 50", (f"%{query_str}%",)).fetchall()
    else:
        res = conn.execute(f"SELECT DISTINCT {column} FROM media WHERE {column} IS NOT NULL ORDER BY {column} LIMIT 50").fetchall()
    conn.close()
    return jsonify([r[0] for r in res if r[0]])

@app.route("/api/delete_face", methods=["POST"])
def delete_face():
    face_id = request.json.get("face_id")
    if not face_id: return jsonify({"error": "Missing ID"}), 400
    conn = get_db_connection()
    conn.execute("DELETE FROM faces WHERE id = ?", (face_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/get_faces")
def get_faces():
    file_path = request.args.get("path")
    if not file_path: return jsonify({"faces": [], "thumb_w": 400, "thumb_h": 400})
    
    conn = get_db_connection()
    media_row = conn.execute("SELECT id FROM media WHERE current_path = ?", (file_path,)).fetchone()
    if not media_row: 
        conn.close()
        return jsonify({"faces": [], "thumb_w": 400, "thumb_h": 400})
        
    media_id = media_row['id']
    
    path_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
    thumb_path = THUMB_DIR / f"{path_hash}.jpg"
    
    tw, th = 400, 400
    
    if thumb_path.exists():
        try:
            # We open it with Pillow first to guarantee we send the exact dimensions to JS
            with Image.open(thumb_path) as img:
                tw, th = img.size
                
            import face_recognition
            image = face_recognition.load_image_file(str(thumb_path))
            
            face_locations = face_recognition.face_locations(image)

            if face_locations:
                db_faces = conn.execute("SELECT box_top, box_left FROM faces WHERE media_id = ? AND box_top IS NOT NULL", (media_id,)).fetchall()
                
                locations_to_insert = []
                for (top, right, bottom, left) in face_locations:
                    is_new = True
                    for db_face in db_faces:
                        if abs(db_face['box_top'] - top) < 15 and abs(db_face['box_left'] - left) < 15:
                            is_new = False
                            break
                    if is_new:
                        locations_to_insert.append((top, right, bottom, left))

                if locations_to_insert:
                    new_encodings = face_recognition.face_encodings(image, known_face_locations=locations_to_insert)
                    for (top, right, bottom, left), encoding in zip(locations_to_insert, new_encodings):
                        conn.execute("""
                            INSERT INTO faces (media_id, box_top, box_right, box_bottom, box_left, encoding, exclude_from_ml)
                            VALUES (?, ?, ?, ?, ?, ?, 0)
                        """, (media_id, top, right, bottom, left, encoding.tobytes()))
                    conn.commit()
        except Exception as e:
            print(f"Live scan engine error: {e}")

    faces = conn.execute("SELECT id, box_top, box_right, box_bottom, box_left, person_name FROM faces WHERE media_id = ? AND box_top IS NOT NULL", (media_id,)).fetchall()
    conn.close()
    
    return jsonify({
        "faces": [dict(f) for f in faces],
        "thumb_w": tw,
        "thumb_h": th
    })

@app.route("/api/tag_specific_face", methods=["POST"])
def tag_specific_face():
    data = request.json
    face_id = data.get("face_id")
    person_name = data.get("person_name")
    exclude_from_ml = 1 if data.get("exclude_from_ml") else 0
    if not face_id or not person_name: return jsonify({"error": "Missing data"}), 400
    conn = get_db_connection()
    conn.execute("UPDATE faces SET person_name = ?, exclude_from_ml = ? WHERE id = ?", (person_name.strip(), exclude_from_ml, face_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/add_custom_face", methods=["POST"])
def add_custom_face():
    data = request.json
    file_path = data.get("path")
    person_name = data.get("person_name")
    box = data.get("box") 
    exclude_from_ml = 1 if data.get("exclude_from_ml") else 0

    if not file_path or not person_name or not box:
        return jsonify({"error": "Missing data"}), 400

    conn = get_db_connection()
    media_row = conn.execute("SELECT id FROM media WHERE current_path = ?", (file_path,)).fetchone()
    if not media_row:
        conn.close()
        return jsonify({"error": "Media not found"}), 404
        
    media_id = media_row['id']
    encoding_blob = None
    top = right = bottom = left = None

    path_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
    thumb_path = THUMB_DIR / f"{path_hash}.jpg"
    
    if thumb_path.exists():
        try:
            import face_recognition
            image = face_recognition.load_image_file(str(thumb_path))
            h, w, _ = image.shape
            
            top = max(0, min(h - 1, int((box['top_pct'] / 100) * h)))
            bottom = max(0, min(h, int((box['bottom_pct'] / 100) * h)))
            left = max(0, min(w - 1, int((box['left_pct'] / 100) * w)))
            right = max(0, min(w, int((box['right_pct'] / 100) * w)))
            
            if top >= bottom or left >= right:
                conn.close()
                return jsonify({"error": "Invalid bounding box area"}), 400
            
            if exclude_from_ml == 0:
                encodings = face_recognition.face_encodings(image, known_face_locations=[(top, right, bottom, left)])
                if encodings:
                    encoding_blob = encodings[0].tobytes()
                else:
                    exclude_from_ml = 1
                    
        except Exception as e:
            exclude_from_ml = 1 

    conn.execute("""
        INSERT INTO faces (media_id, person_name, exclude_from_ml, box_top, box_right, box_bottom, box_left, encoding) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (media_id, person_name.strip(), exclude_from_ml, top, right, bottom, left, encoding_blob))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/add_manual_tag", methods=["POST"])
def add_manual_tag():
    data = request.json
    file_paths = data.get("paths", [])
    person_name = data.get("person_name")
    exclude_from_ml = 1 if data.get("exclude_from_ml") else 0
    if not file_paths or not person_name: return jsonify({"error": "Missing data"}), 400

    conn = get_db_connection()
    for file_path in file_paths:
        media_row = conn.execute("SELECT id FROM media WHERE current_path = ?", (file_path,)).fetchone()
        if not media_row: continue
        media_id = media_row[0]
        person_clean = person_name.strip()
        
        existing = conn.execute("SELECT id FROM faces WHERE media_id = ? AND person_name = ?", (media_id, person_clean)).fetchone()
        if existing:
            conn.execute("UPDATE faces SET exclude_from_ml = ? WHERE id = ?", (exclude_from_ml, existing[0]))
            continue

        if exclude_from_ml == 0:
            ml_faces = conn.execute("SELECT id FROM faces WHERE media_id = ? AND encoding IS NOT NULL", (media_id,)).fetchall()
            if len(ml_faces) == 1:
                conn.execute("UPDATE faces SET person_name = ?, exclude_from_ml = 0 WHERE id = ?", (person_clean, ml_faces[0][0]))
            else:
                conn.execute("INSERT INTO faces (media_id, person_name, exclude_from_ml) VALUES (?, ?, ?)", (media_id, person_clean, exclude_from_ml))
        else:
            conn.execute("INSERT INTO faces (media_id, person_name, exclude_from_ml) VALUES (?, ?, 1)", (media_id, person_clean))
            
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/name_cluster", methods=["POST"])
def name_cluster():
    data = request.json
    if data.get("cluster_id") is None or not data.get("person_name"): 
        return jsonify({"error": "Invalid data"}), 400
    conn = get_db_connection()
    conn.execute("UPDATE faces SET person_name = ? WHERE cluster_id = ?", (data["person_name"].strip(), data["cluster_id"]))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

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

@app.route("/people")
def people_manager():
    conn = get_db_connection()
    unnamed = conn.execute("SELECT f.cluster_id, COUNT(f.id) as face_count, m.current_path as sample_path, m.file_type FROM faces f JOIN media m ON f.media_id = m.id WHERE f.person_name IS NULL AND f.cluster_id != -1 AND f.exclude_from_ml = 0 GROUP BY f.cluster_id ORDER BY face_count DESC").fetchall()
    named = conn.execute("SELECT f.person_name, COUNT(f.id) as face_count, MIN(m.current_path) as sample_path, m.file_type FROM faces f JOIN media m ON f.media_id = m.id WHERE f.person_name IS NOT NULL GROUP BY f.person_name ORDER BY f.person_name ASC").fetchall()
    conn.close()
    return render_template_string(PEOPLE_HTML_TEMPLATE, unnamed=unnamed, named=named)

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
    person = request.args.get("person", "") 
    
    sort_param = request.args.get("sort", "date_desc")
    sort_mapping = {
        "date_desc": "date_taken DESC", "date_asc": "date_taken ASC", 
        "size_desc": "file_size_kb DESC", "size_asc": "file_size_kb ASC"
    }
    order_by_clause = sort_mapping.get(sort_param, "date_taken DESC")

    conditions = ""
    params = []
    
    if person:
        if person.startswith("cluster:"):
            conditions += " AND media.id IN (SELECT media_id FROM faces WHERE cluster_id = ?)"
            params.append(int(person.split(":")[1]))
        else:
            for p in [p.strip() for p in person.split(",") if p.strip()]:
                conditions += " AND media.id IN (SELECT media_id FROM faces WHERE person_name LIKE ?)"
                params.append(f"%{p}%")

    if source: conditions += " AND source = ?"; params.append(source)
    if camera: conditions += " AND camera_model LIKE ?"; params.append(f"%{camera}%")
    if location: conditions += " AND location_name LIKE ?"; params.append(f"%{location}%")
    if start_date: conditions += " AND date_taken >= ?"; params.append(start_date + " 00:00:00")
    if end_date: conditions += " AND date_taken <= ?"; params.append(end_date + " 23:59:59")
    if name: conditions += " AND original_name LIKE ?"; params.append(f"%{name}%")
    if file_type: conditions += " AND file_type = ?"; params.append(file_type)
    
    conn = get_db_connection()
    total_count = conn.execute(f"SELECT COUNT(*) FROM media WHERE 1=1 {conditions}", params).fetchone()[0]
    
    per_page = 200
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page
    
    data_query = f"""
        SELECT 
            media.id, media.original_name, media.current_path, media.file_type, media.source, 
            media.date_taken, media.camera_model, media.file_size_kb, media.location_name,
            (SELECT GROUP_CONCAT(DISTINCT person_name) FROM faces WHERE media_id = media.id AND person_name IS NOT NULL) AS people
        FROM media WHERE 1=1 {conditions} ORDER BY {order_by_clause} LIMIT {per_page} OFFSET ?
    """
    
    results = conn.execute(data_query, params + [offset]).fetchall()
    conn.close()
    
    return render_template_string(HTML_TEMPLATE, results=results, page=page, total_pages=total_pages, total_count=total_count)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
