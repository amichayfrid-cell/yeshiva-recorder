// State
let pendingLessons = [];
let currentPendingSource = null;
let allNotes = [];
let activeCardIndex = null;
let currentFolderData = null;
let currentAudio = null;
let currentPlayBtn = null;
let highlightedFolderIndex = 0;

// Initialization
document.addEventListener("DOMContentLoaded", () => {
    loadPendingLessons();
    loadNotes();
    setupKeyboardListeners();
});

// Refresh all views
function refreshAll() {
    loadPendingLessons();
    loadNotes();
}

// Tab Switching
function switchTab(tab) {
    document.getElementById("view-pending").style.display = tab === "pending" ? "block" : "none";
    document.getElementById("view-notes").style.display = tab === "notes" ? "block" : "none";
    
    document.getElementById("tab-pending-btn").classList.toggle("active", tab === "pending");
    document.getElementById("tab-notes-btn").classList.toggle("active", tab === "notes");
}

// Fetch Pending Lessons
async function loadPendingLessons() {
    const listContainer = document.getElementById("lessons-list");
    listContainer.innerHTML = `<div class="empty-state"><div class="icon">⏳</div><h3>טוען שיעורים...</h3></div>`;

    try {
        const res = await fetch("/api/lessons/pending");
        if (res.status === 401) {
            sessionStorage.removeItem("last_yeshiva_folder_path");
            window.location.href = "/login";
            return;
        }
        const data = await res.json();
        pendingLessons = data.lessons || [];

        document.getElementById("pending-count").innerText = pendingLessons.length;
        renderPendingFolders();
        renderPendingLessons();
    } catch (e) {
        listContainer.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><h3>שגיאה בטעינת השיעורים</h3><p>${e.message}</p></div>`;
    }
}

// Render Folder Cards (like Rav Tzvi)
function renderPendingFolders() {
    const foldersSection = document.getElementById("pending-folders-section");
    const foldersGrid = document.getElementById("pending-folders-grid");
    const folderBar = document.getElementById("current-folder-bar");
    if (!foldersSection || !foldersGrid) return;

    if (pendingLessons.length === 0) {
        foldersSection.style.display = "none";
        if (folderBar) folderBar.style.display = "none";
        return;
    }

    foldersSection.style.display = "block";

    const uploadCount = pendingLessons.filter(l => l.source === 'upload').length;
    const recorderCount = pendingLessons.filter(l => l.source !== 'upload').length;

    const uploadSubText = uploadCount > 0 ? `${uploadCount} שיעורים` : 'אין שיעורים';
    const recorderSubText = recorderCount > 0 ? `${recorderCount} שיעורים` : 'אין שיעורים';

    foldersGrid.innerHTML = `
        <div class="folder-card ${currentPendingSource === 'upload' ? 'selected' : ''}" onclick="selectPendingFolder('upload')">
            <span class="folder-icon">📁</span>
            <div style="flex: 1; min-width: 0;">
                <div class="folder-name" title="העלאת שיעורים">העלאת שיעורים</div>
                <div class="folder-sub">${uploadSubText}</div>
            </div>
        </div>
        <div class="folder-card ${currentPendingSource === 'recorder' ? 'selected' : ''}" onclick="selectPendingFolder('recorder')">
            <span class="folder-icon">📁</span>
            <div style="flex: 1; min-width: 0;">
                <div class="folder-name" title="שיעורים למיון (מקלט שמע)">שיעורים למיון (מקלט שמע)</div>
                <div class="folder-sub">${recorderSubText}</div>
            </div>
        </div>
    `;

    renderFolderBar(uploadCount, recorderCount);
}

function selectPendingFolder(source) {
    if (currentPendingSource === source) {
        currentPendingSource = null;
    } else {
        currentPendingSource = source;
    }
    renderPendingFolders();
    renderPendingLessons();
}

function renderFolderBar(uploadCount, recorderCount) {
    const folderBar = document.getElementById("current-folder-bar");
    const breadcrumbs = document.getElementById("pending-breadcrumbs");
    const btnClose = document.getElementById("btn-close-folder") || document.getElementById("btn-show-all-folders");
    if (!folderBar || !breadcrumbs) return;

    if (!currentPendingSource) {
        folderBar.style.display = "none";
        return;
    }

    folderBar.style.display = "flex";

    if (currentPendingSource === 'upload') {
        breadcrumbs.innerHTML = `
            <span class="breadcrumb-crumb" onclick="selectPendingFolder(null)" title="חזור לכל התיקיות">📁 תיקיות</span>
            <span class="breadcrumb-sep">❮</span>
            <span>📤 העלאת שיעורים (${uploadCount} שיעורים)</span>
        `;
    } else if (currentPendingSource === 'recorder') {
        breadcrumbs.innerHTML = `
            <span class="breadcrumb-crumb" onclick="selectPendingFolder(null)" title="חזור לכל התיקיות">📁 תיקיות</span>
            <span class="breadcrumb-sep">❮</span>
            <span>🎙️ שיעורים למיון - מקלט שמע (${recorderCount} שיעורים)</span>
        `;
    }

    if (btnClose) {
        btnClose.style.display = "inline-flex";
        btnClose.innerHTML = "✕ סגור הכל";
        btnClose.onclick = () => selectPendingFolder(null);
    }
}

// Render Pending Lessons
function renderPendingLessons() {
    const listContainer = document.getElementById("lessons-list");
    if (pendingLessons.length === 0) {
        listContainer.innerHTML = `
            <div class="empty-state">
                <div class="icon">🎉</div>
                <h3>אין שיעורים הממתינים למיון</h3>
                <p>כל השיעורים מוינו בהצלחה! שיעורים חדשים יופיעו כאן מיד עם חיבור מקלט שמע או העלאה לתיקיית העלאת שיעורים.</p>
            </div>
        `;
        return;
    }

    // By default, do not display lessons until user clicks into a folder
    if (!currentPendingSource) {
        listContainer.innerHTML = `
            <div class="empty-state" style="padding: 2.75rem 1.5rem; background: #ffffff; border: 1px dashed var(--border); border-radius: var(--radius); box-shadow: var(--shadow);">
                <div class="icon" style="font-size: 2.8rem; margin-bottom: 0.75rem;">📂</div>
                <h3 style="font-size: 1.2rem; color: var(--text-main); margin-bottom: 0.4rem;">בחר תיקייה כדי להתחיל במיון השיעורים</h3>
                <p style="color: var(--text-muted); font-size: 0.95rem; margin: 0 auto; max-width: 480px; line-height: 1.5;">לחץ על אחת התיקיות למעלה (<strong>העלאת שיעורים</strong> או <strong>שיעורים למיון</strong>) כדי להיכנס ולסווג את השיעורים הממתינים בה.</p>
            </div>
        `;
        return;
    }

    let filtered = pendingLessons.filter(l => currentPendingSource === 'upload' ? l.source === 'upload' : l.source !== 'upload');

    if (filtered.length === 0) {
        const folderTitle = currentPendingSource === 'upload' ? 'העלאת שיעורים' : 'שיעורים למיון (מקלט שמע)';
        listContainer.innerHTML = `
            <div class="empty-state">
                <div class="icon">📁</div>
                <h3>אין שיעורים בתיקיית '${folderTitle}'</h3>
                <p>כל השיעורים בתיקייה זו מוינו בהצלחה.</p>
                <div style="margin-top: 1rem;">
                    <button class="btn btn-outline" onclick="selectPendingFolder(null)">
                        ✕ סגור הכל
                    </button>
                </div>
            </div>
        `;
        return;
    }

    listContainer.innerHTML = filtered.map(lesson => {
        const index = pendingLessons.indexOf(lesson);
        const notesHtml = (lesson.notes && lesson.notes.length > 0) ? lesson.notes.map(note => `
            <div class="student-note-banner" id="note-banner-${note.id}">
                <span class="icon">🔔</span>
                <div style="flex: 1; min-width: 0;">
                    <div class="note-content"><strong>הערת תלמיד:</strong> ${escapeHtml(note.description)}</div>
                    <div class="note-meta" title="${escapeHtml(note.created_at || '')}">נשלח ע"י ${escapeHtml(note.student_name)} | ${escapeHtml(formatNoteDateDisplay(note))}</div>
                </div>
                <button type="button" class="btn btn-outline btn-sm" onclick="resolveNote(${note.id})" style="align-self: center; margin-right: auto; padding: 4px 10px; font-size: 0.8rem; background: #ffffff; border-color: #fde047; color: #854d0e; cursor: pointer; white-space: nowrap; border-radius: 6px;" title="סמן הערה זו כטופלה">✓ סמן כטופל</button>
            </div>
        `).join("") : "";

        const sourceBadge = lesson.source === 'upload'
            ? `<span class="badge badge-source-upload" title="שיעור שהועלה לתיקיית העלאת שיעורים">📤 העלאת שיעורים</span>`
            : `<span class="badge badge-source-recorder" title="שיעור שנקלט ישירות ממקלט שמע (USB)">🎙️ מקלט שמע</span>`;

        return `
            <div class="lesson-card" id="card-${index}">
                <div class="card-header">
                    <div class="card-title-wrap">
                        ${sourceBadge}
                        <span class="badge badge-hebrew-date">${escapeHtml(lesson.hebrew_date)}</span>
                        <span class="badge badge-time">שעת הקלטה: <bdi dir="ltr">${escapeHtml(lesson.created_time)}</bdi></span>
                        <span class="badge badge-time">${lesson.size_mb} MB</span>
                        <span class="card-title" dir="ltr" style="unicode-bidi: isolate;"><bdi>${escapeHtml(lesson.filename)}</bdi></span>
                    </div>
                </div>

                ${notesHtml}

                <!-- Audio Player -->
                <div class="player-container">
                    <div class="audio-controls">
                        <button class="btn-icon btn-skip" onclick="skipAudio('${index}', -10)" title="10 שניות אחורה"><span>⏪</span><span>10</span></button>
                        <button class="btn-icon btn-play" id="play-btn-${index}" onclick="togglePlay('${index}')">▶</button>
                        <button class="btn-icon btn-skip" onclick="skipAudio('${index}', 10)" title="10 שניות קדימה"><span>10</span><span>⏩</span></button>
                    </div>
                    <div class="progress-wrap">
                        <input type="range" class="seek-bar" id="seek-${index}" value="0" min="0" step="0.1" onchange="seekAudio('${index}')">
                        <span class="time-display" id="time-${index}">00:00 / --:--</span>
                    </div>
                    <audio id="audio-${index}" src="/api/audio/stream?filename=${encodeURIComponent(lesson.filename).replace(/'/g, '%27')}&source_path=${encodeURIComponent(lesson.full_path || '').replace(/'/g, '%27')}" preload="none" ontimeupdate="updateProgress('${index}')" onloadedmetadata="initAudioDuration('${index}')" onended="onAudioEnded('${index}')"></audio>
                </div>

                <!-- Classification Form Grid -->
                <div class="form-grid">
                    <div class="form-field">
                        <label>שם הרב:</label>
                        <input type="text" class="input-text" id="rabbi-${index}" placeholder="למשל: הרב אורי" required>
                    </div>
                    <div class="form-field">
                        <label>נושא / שם השיעור:</label>
                        <input type="text" class="input-text" id="topic-${index}" placeholder="למשל: פרשת כי תצא">
                    </div>
                    <div class="form-field">
                        <label>תאריך עברי:</label>
                        <input type="text" class="input-text" id="date-${index}" value="${escapeHtml(lesson.hebrew_date)}">
                    </div>
                    <div class="form-field">
                        <label>תיקיית יעד בשרת:</label>
                        <div class="folder-picker-wrap">
                            <button type="button" class="folder-select-btn" id="folder-btn-${index}" onclick="openFolderExplorer('${index}')">
                                <span id="folder-label-${index}">בחר תיקיית יעד...</span>
                                <span>📁 ▾</span>
                            </button>
                            <input type="hidden" id="dest-path-${index}">
                        </div>
                    </div>
                    <div style="display: flex; gap: 0.5rem;">
                        <button class="btn btn-success" onclick="classifyLesson('${index}', '${encodeURIComponent(lesson.filename).replace(/'/g, '%27')}', '${encodeURIComponent(lesson.full_path || '').replace(/'/g, '%27')}')">
                            💾 שמור וסווג
                        </button>
                        <button type="button" class="btn btn-danger" onclick="deleteLesson('${index}', '${encodeURIComponent(lesson.filename).replace(/'/g, '%27')}', '${encodeURIComponent(lesson.full_path || '').replace(/'/g, '%27')}')" title="מחק הקלטה לצמיתות">
                            🗑️ מחק
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

// Audio Controls
function togglePlay(index) {
    const audio = document.getElementById(`audio-${index}`);
    const btn = document.getElementById(`play-btn-${index}`);

    if (currentAudio && currentAudio !== audio) {
        currentAudio.pause();
        if (currentPlayBtn) currentPlayBtn.innerText = "▶";
    }

    if (audio.paused) {
        audio.play().catch(e => console.warn("Play interrupted:", e));
        btn.innerText = "⏸";
        currentAudio = audio;
        currentPlayBtn = btn;
    } else {
        audio.pause();
        btn.innerText = "▶";
    }
}

function skipAudio(index, seconds) {
    const audio = document.getElementById(`audio-${index}`);
    if (audio) {
        audio.currentTime = Math.max(0, Math.min(audio.duration || 0, audio.currentTime + seconds));
    }
}

function updateProgress(index) {
    const audio = document.getElementById(`audio-${index}`);
    const seek = document.getElementById(`seek-${index}`);
    const timeDisplay = document.getElementById(`time-${index}`);

    if (audio && audio.duration && isFinite(audio.duration)) {
        seek.value = (audio.currentTime / audio.duration) * 100;
        timeDisplay.innerText = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
    } else if (audio && !isNaN(audio.currentTime)) {
        timeDisplay.innerText = `${formatTime(audio.currentTime)} / --:--`;
    }
}

function initAudioDuration(index) {
    const audio = document.getElementById(`audio-${index}`);
    const timeDisplay = document.getElementById(`time-${index}`);
    if (audio && audio.duration && isFinite(audio.duration)) {
        timeDisplay.innerText = `00:00 / ${formatTime(audio.duration)}`;
    }
}

function seekAudio(index) {
    const audio = document.getElementById(`audio-${index}`);
    const seek = document.getElementById(`seek-${index}`);
    if (audio && audio.duration && isFinite(audio.duration)) {
        audio.currentTime = (seek.value / 100) * audio.duration;
    }
}

function onAudioEnded(index) {
    const btn = document.getElementById(`play-btn-${index}`);
    if (btn) btn.innerText = "▶";
}

function formatTime(seconds) {
    if (isNaN(seconds) || !isFinite(seconds)) return "00:00";
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min < 10 ? '0' : ''}${min}:${sec < 10 ? '0' : ''}${sec}`;
}

// --- Instant Folder Explorer with Keyboard Navigation ---
let modalAudioInstance = null;
let currentModalAudioBtnId = null;

function getStoredFolderPath() {
    try {
        return sessionStorage.getItem("last_yeshiva_folder_path") || "";
    } catch (e) {
        return "";
    }
}

function setStoredFolderPath(fullPath, isRoot) {
    try {
        if (isRoot || !fullPath) {
            sessionStorage.setItem("last_yeshiva_folder_path", "");
        } else {
            sessionStorage.setItem("last_yeshiva_folder_path", fullPath);
        }
    } catch (e) {
        console.warn("Storage error:", e);
    }
}

function stopModalAudioPreview() {
    if (modalAudioInstance) {
        modalAudioInstance.pause();
        modalAudioInstance = null;
    }
    if (currentModalAudioBtnId) {
        const prevBtn = document.getElementById(currentModalAudioBtnId);
        if (prevBtn) {
            prevBtn.innerHTML = "▶ השמע";
            prevBtn.classList.remove("playing");
        }
        currentModalAudioBtnId = null;
    }
}

function toggleModalAudioPreview(encodedName, btnId) {
    const filename = decodeURIComponent(encodedName);
    const btn = document.getElementById(btnId);
    if (!currentFolderData) return;

    const fullPath = (currentFolderData.current_full_path || "") + "/" + filename;
    const streamUrl = `/api/audio/stream?filename=${encodeURIComponent(filename)}&source_path=${encodeURIComponent(fullPath)}`;

    if (modalAudioInstance && !modalAudioInstance.paused && currentModalAudioBtnId === btnId) {
        stopModalAudioPreview();
        return;
    }

    stopModalAudioPreview();

    modalAudioInstance = new Audio(streamUrl);
    currentModalAudioBtnId = btnId;
    if (btn) {
        btn.innerHTML = "⏸ עצור";
        btn.classList.add("playing");
    }

    modalAudioInstance.play().catch(e => {
        console.warn("Playback failed:", e);
        stopModalAudioPreview();
    });

    modalAudioInstance.onended = () => {
        stopModalAudioPreview();
    };
}

function navigateToBreadcrumb(index) {
    if (window.modalBreadcrumbs && window.modalBreadcrumbs[index] !== undefined) {
        fetchFolderContent(window.modalBreadcrumbs[index].path);
    }
}

async function fetchFolderContent(path = "") {
    stopModalAudioPreview();
    const listContainer = document.getElementById("modal-folders-list");
    listContainer.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">טוען תיקייה...</div>`;

    try {
        const res = await fetch("/api/folders/list", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: path || null })
        });
        if (res.status === 401) {
            setStoredFolderPath("", true);
            window.location.href = "/login";
            return;
        }
        const data = await res.json();
        if (data && data.subfolders) {
            data.subfolders = data.subfolders.filter(sub => !sub.name.includes("הגברת החירות"));
        }
        currentFolderData = data;
        if (data) { 
            setStoredFolderPath(data.current_full_path, data.is_root); 
        }
        highlightedFolderIndex = 0;
        renderExplorerView();
    } catch (e) {
        listContainer.innerHTML = `<div style="color:var(--danger); padding:1rem;">שגיאה: ${e.message}</div>`;
    }
}


// ==========================================
// Folder Modal Search Functionality
// ==========================================
let folderSearchTimer = null;
let currentFolderSearchResults = null;
let highlightedSearchResultIndex = 0;

function handleFolderSearchInput() {
    const input = document.getElementById("modal-folder-search-input");
    const clearBtn = document.getElementById("modal-search-clear-btn");
    if (!input) return;
    const q = input.value.trim();

    if (!q) {
        clearFolderSearch(true);
        return;
    }

    if (clearBtn) clearBtn.style.display = "flex";

    // 1. Instant local filter if currently in a folder with subfolders
    const currentSubfolders = (currentFolderData && currentFolderData.subfolders) ? currentFolderData.subfolders : [];
    const localFiltered = currentSubfolders.filter(s => s.name.toLowerCase().includes(q.toLowerCase()));

    renderFolderSearchResults(localFiltered, q, true);

    // 2. Global search across all folders on the server (debounced)
    clearTimeout(folderSearchTimer);
    if (q.length >= 2) {
        folderSearchTimer = setTimeout(async () => {
            try {
                const res = await fetch(`/api/folders/search?q=${encodeURIComponent(q)}`);
                if (res.status === 401) {
                    window.location.href = "/login";
                    return;
                }
                const data = await res.json();
                if (document.getElementById("modal-folder-search-input") && document.getElementById("modal-folder-search-input").value.trim() === q) {
                    currentFolderSearchResults = (data.results || []).filter(item => !item.name.includes("הגברת החירות"));
                    highlightedSearchResultIndex = 0;
                    renderFolderSearchResults(currentFolderSearchResults, q, false);
                }
            } catch (err) {
                console.warn("Folder search failed:", err);
            }
        }, 220);
    }
}

function clearFolderSearch(shouldRender = true) {
    const input = document.getElementById("modal-folder-search-input");
    const clearBtn = document.getElementById("modal-search-clear-btn");
    if (input) input.value = "";
    if (clearBtn) clearBtn.style.display = "none";
    clearTimeout(folderSearchTimer);
    currentFolderSearchResults = null;
    highlightedSearchResultIndex = 0;
    if (shouldRender) {
        renderExplorerView();
    }
}

function renderFolderSearchResults(results, query, isLocalOnly = false) {
    const listContainer = document.getElementById("modal-folders-list");
    if (!listContainer) return;

    if (!results || results.length === 0) {
        listContainer.innerHTML = `
            <div style="text-align: center; padding: 2.5rem 1rem; color: var(--text-muted);">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔍</div>
                <div style="font-weight: 600; font-size: 1rem; color: var(--text-main); margin-bottom: 0.25rem;">
                    לא נמצאו תיקיות עבור "${escapeHtml(query)}"
                </div>
                <div style="font-size: 0.85rem;">
                    נסה לחפש במילים קצרות יותר, או צור תיקייה חדשה למטה
                </div>
            </div>
        `;
        return;
    }

    const countLabel = isLocalOnly 
        ? `${results.length} תיקיות בתיקייה זו` 
        : `${results.length} תיקיות ברחבי השרת`;

    let html = `
        <div class="search-results-header">
            <span>תוצאות חיפוש עבור "<strong>${escapeHtml(query)}</strong>" (${countLabel}):</span>
            <button type="button" class="btn btn-sm btn-outline" onclick="clearFolderSearch(true)" style="padding: 2px 8px; font-size: 0.75rem;">חזור לתצוגה רגילה</button>
        </div>
    `;

    html += results.map((item, idx) => {
        const isHighlighted = idx === highlightedSearchResultIndex;
        const displayPath = item.breadcrumb || item.rel_path || item.name;
        const safeFull = encodeURIComponent(item.full_path).replace(/'/g, "%27");
        const safeRel = encodeURIComponent(item.rel_path || item.name).replace(/'/g, "%27");

        return `
            <div class="search-result-row ${isHighlighted ? 'highlighted' : ''}" 
                 id="search-res-${idx}" 
                 onclick="enterSearchResultFolder('${safeFull}')"
                 onmouseenter="highlightedSearchResultIndex = ${idx}; updateSearchHighlightedUI();">
                <div class="search-result-main">
                    <div class="search-result-title">
                        <span>📁</span>
                        <span>${escapeHtml(item.name)}</span>
                    </div>
                    <div class="search-result-path" title="${escapeHtml(displayPath)}">
                        ${escapeHtml(displayPath)}
                    </div>
                </div>
                <div class="search-result-actions" onclick="event.stopPropagation();">
                    <button type="button" 
                            class="btn-select-search-result" 
                            onclick="confirmDirectFolderSelection('${safeFull}', '${safeRel}')"
                            title="בחר תיקייה זו כתיקיית יעד וסגור">
                        ✓ בחר תיקייה זו
                    </button>
                    <button type="button" 
                            class="btn-enter-search-result" 
                            onclick="enterSearchResultFolder('${safeFull}')"
                            title="פתח תיקייה זו בסייר">
                        היכנס ❮
                    </button>
                </div>
            </div>
        `;
    }).join("");

    listContainer.innerHTML = html;
}

function enterSearchResultFolder(encodedFull) {
    const full = decodeURIComponent(encodedFull);
    clearFolderSearch(false);
    fetchFolderContent(full);
}

function confirmDirectFolderSelection(encodedFull, encodedRel) {
    const full = decodeURIComponent(encodedFull);
    const rel = decodeURIComponent(encodedRel);

    if (activeCardIndex === "edit-modal") {
        document.getElementById("edit-lesson-dest-path").value = full;
        document.getElementById("edit-lesson-folder-label").innerText = rel || "ראשי (שרת הישיבה)";
    } else if (activeCardIndex !== null) {
        document.getElementById(`dest-path-${activeCardIndex}`).value = full;
        document.getElementById(`folder-label-${activeCardIndex}`).innerText = rel || "ראשי (שורש)";
    }
    setStoredFolderPath(full, false);
    closeFolderModal();
}

function updateSearchHighlightedUI() {
    const rows = document.querySelectorAll(".search-result-row");
    rows.forEach((row, i) => {
        row.classList.toggle("highlighted", i === highlightedSearchResultIndex);
    });
}

function handleFolderSearchKeyDown(e) {
    if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        clearFolderSearch(true);
        return;
    }

    if (currentFolderSearchResults && currentFolderSearchResults.length > 0) {
        if (e.key === "ArrowDown") {
            e.preventDefault();
            highlightedSearchResultIndex = (highlightedSearchResultIndex + 1) % currentFolderSearchResults.length;
            updateSearchHighlightedUI();
            const el = document.getElementById(`search-res-${highlightedSearchResultIndex}`);
            if (el) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            highlightedSearchResultIndex = (highlightedSearchResultIndex - 1 + currentFolderSearchResults.length) % currentFolderSearchResults.length;
            updateSearchHighlightedUI();
            const el = document.getElementById(`search-res-${highlightedSearchResultIndex}`);
            if (el) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
        } else if (e.key === "Enter") {
            e.preventDefault();
            const item = currentFolderSearchResults[highlightedSearchResultIndex];
            if (item) {
                if (e.ctrlKey) {
                    confirmDirectFolderSelection(encodeURIComponent(item.full_path), encodeURIComponent(item.rel_path || item.name));
                } else {
                    enterSearchResultFolder(encodeURIComponent(item.full_path));
                }
            }
        }
    }
}

function openFolderExplorer(cardIndex) {
    activeCardIndex = cardIndex;
    clearFolderSearch(false);
    const currentStoredPath = getStoredFolderPath();
    fetchFolderContent(currentStoredPath);
    document.getElementById("folder-modal").classList.add("open");
}

function closeFolderModal() {
    stopModalAudioPreview();
    clearFolderSearch(false);
    if (currentFolderData) {
        setStoredFolderPath(currentFolderData.current_full_path, currentFolderData.is_root);
    }
    document.getElementById("folder-modal").classList.remove("open");
    activeCardIndex = null;
}

function renderExplorerView() {
    if (!currentFolderData) return;

    const breadcrumbsContainer = document.getElementById("modal-breadcrumbs");
    const listContainer = document.getElementById("modal-folders-list");

    // 1. Interactive Breadcrumbs Trail (Functions as Navigation & Back Button)
    let parts = currentFolderData.current_rel_path ? currentFolderData.current_rel_path.replace(/\\/g, "/").split("/").filter(Boolean) : [];

    const rootPath = currentFolderData.root_full_path || (currentFolderData.is_root ? currentFolderData.current_full_path : currentFolderData.current_full_path.slice(0, currentFolderData.current_full_path.length - (currentFolderData.current_rel_path || "").length).replace(/[\\/]$/, ""));

    window.modalBreadcrumbs = [];
    window.modalBreadcrumbs.push({ name: "שרת הישיבה (ראשי)", path: rootPath });

    let accumulatedPath = rootPath;
    parts.forEach((part) => {
        accumulatedPath += "/" + part;
        window.modalBreadcrumbs.push({ name: part, path: accumulatedPath });
    });

    let crumbsHtml = "";
    if (parts.length > 0) {
        const parentCrumbIndex = window.modalBreadcrumbs.length - 2;
        crumbsHtml += `
            <button type="button" 
                    class="btn-crumb-up" 
                    onclick="navigateToBreadcrumb(${parentCrumbIndex})" 
                    title="חזור תיקייה אחת אחורה">
                <span>↩</span>
                <span>אחורה</span>
            </button>
            <span class="crumb-separator" style="opacity: 0.4;">|</span>
        `;
    }

    crumbsHtml += window.modalBreadcrumbs.map((crumb, idx) => {
        const isLast = idx === window.modalBreadcrumbs.length - 1;
        const icon = idx === 0 ? "🏢" : "📁";
        return `
            ${idx > 0 ? `<span class="crumb-separator">❯</span>` : ''}
            <button type="button" 
                    class="crumb-btn ${isLast ? 'active-crumb' : ''}" 
                    onclick="navigateToBreadcrumb(${idx})"
                    title="${isLast ? 'תיקייה נוכחית' : `חזור לתיקיית ${escapeHtml(crumb.name)}`}">
                <span>${icon}</span>
                <span>${escapeHtml(crumb.name)}</span>
            </button>
        `;
    }).join("");

    breadcrumbsContainer.innerHTML = crumbsHtml;

    // 2. Beautiful Existing Audio Files in current folder
    const audioFiles = currentFolderData.audio_files || [];
    let audioFilesHtml = "";
    if (audioFiles.length > 0) {
        audioFilesHtml = `
            <div class="existing-lessons-panel">
                <div class="existing-lessons-header">
                    <div class="existing-lessons-title">
                        <span class="icon">🎙️</span>
                        <span>שיעורים קיימים בתיקייה זו</span>
                    </div>
                    <span class="existing-lessons-badge">${audioFiles.length} שיעורים</span>
                </div>
                <div class="existing-lessons-list">
                    ${audioFiles.map((name, i) => {
                        const cleanName = name.replace(/\.(mp3|wav|m4a|ogg)$/i, "");
                        const ext = (name.split('.').pop() || 'MP3').toUpperCase();
                        return `
                            <div class="existing-lesson-item">
                                <div class="existing-lesson-main">
                                    <span class="existing-lesson-icon">🎵</span>
                                    <div class="existing-lesson-info">
                                        <div class="existing-lesson-name" title="${escapeHtml(name)}">${escapeHtml(cleanName)}</div>
                                        <span class="existing-lesson-ext">${ext}</span>
                                    </div>
                                </div>
                                <button type="button" 
                                        class="btn-preview-audio" 
                                        id="preview-btn-${i}"
                                        onclick="toggleModalAudioPreview('${encodeURIComponent(name).replace(/'/g, "%27")}', 'preview-btn-${i}')"
                                        title="השמע שיעור">
                                    ▶ השמע
                                </button>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }

    const subfolders = (currentFolderData.subfolders || []).filter(sub => !sub.name.includes("הגברת החירות"));

    if (subfolders.length === 0) {
        listContainer.innerHTML = audioFilesHtml + `
            <div class="empty-folder-hint">
                📁 אין תת-תיקיות נוספות בתוך '${escapeHtml(currentFolderData.current_name)}'.<br>
                <div style="margin-top: 1rem;">
                    <button class="btn btn-primary" onclick="confirmCurrentFolderSelection()">
                        ✓ לחץ כאן (או Enter) לבחירה בתיקייה זו
                    </button>
                </div>
            </div>
        `;
        return;
    }

    listContainer.innerHTML = audioFilesHtml + subfolders.map((sub, idx) => `
        <div class="folder-row ${idx === highlightedFolderIndex ? 'highlighted' : ''}" 
             id="folder-item-${idx}" 
             onclick="handleItemClick(${idx})"
             onmouseenter="setHighlightedIndex(${idx})">
            <div style="display: flex; align-items: center; gap: 0.6rem; min-width: 0; flex: 1;">
                <span style="flex-shrink: 0;">📁</span>
                <span style="font-weight: 500; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; word-break: break-word; line-height: 1.35;">${escapeHtml(sub.name)}</span>
            </div>
            <span style="color: var(--text-muted); font-size: 0.85rem;">היכנס ❮</span>
        </div>
    `).join("");

    scrollHighlightedIntoView();
}

function handleItemClick(index) {
    if (!currentFolderData) return;
    const subfolders = currentFolderData.subfolders || [];
    const item = subfolders[index];
    if (item) {
        fetchFolderContent(item.full_path);
    }
}

function setHighlightedIndex(index) {
    highlightedFolderIndex = index;
    updateHighlightedUI();
}

function updateHighlightedUI() {
    const rows = document.querySelectorAll(".folder-row");
    rows.forEach((row, i) => {
        row.classList.toggle("highlighted", i === highlightedFolderIndex);
    });
}

function scrollHighlightedIntoView() {
    const el = document.getElementById(`folder-item-${highlightedFolderIndex}`);
    if (el) {
        el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
}

// Keyboard Navigation Listener
function setupKeyboardListeners() {
    window.addEventListener("keydown", (e) => {
        const modal = document.getElementById("folder-modal");
        if (!modal.classList.contains("open")) return;

        // If typing in new folder input or search input, allow normal typing
        if (document.activeElement === document.getElementById("modal-folder-search-input")) {
            return;
        }
        if (document.activeElement === document.getElementById("new-folder-input")) {
            if (e.key === "Enter") {
                createNewFolderInCurrentDir();
            }
            return;
        }

        const subfolders = (currentFolderData && currentFolderData.subfolders) ? currentFolderData.subfolders : [];

        if (e.key === "ArrowDown") {
            e.preventDefault();
            if (subfolders.length > 0) {
                highlightedFolderIndex = (highlightedFolderIndex + 1) % subfolders.length;
                updateHighlightedUI();
                scrollHighlightedIntoView();
            }
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            if (subfolders.length > 0) {
                highlightedFolderIndex = (highlightedFolderIndex - 1 + subfolders.length) % subfolders.length;
                updateHighlightedUI();
                scrollHighlightedIntoView();
            }
        } else if (e.key === "Enter" || e.key === "ArrowLeft") {
            e.preventDefault();
            if (e.ctrlKey) {
                // Ctrl+Enter: confirm selection immediately
                confirmCurrentFolderSelection();
            } else if (subfolders.length > 0) {
                handleItemClick(highlightedFolderIndex);
            } else {
                // Leaf folder -> Select it directly on Enter!
                confirmCurrentFolderSelection();
            }
        } else if (e.key === "Backspace" || e.key === "ArrowRight") {
            e.preventDefault();
            if (currentFolderData && currentFolderData.parent_path) {
                fetchFolderContent(currentFolderData.parent_path);
            }
        } else if (e.key === "Escape") {
            closeFolderModal();
        }
    });
}

function fetchFolderByRelativePath(relPath) {
    fetchFolderContent(relPath);
}

function confirmCurrentFolderSelection() {
    if (activeCardIndex === "edit-modal" && currentFolderData) {
        document.getElementById("edit-lesson-dest-path").value = currentFolderData.current_full_path;
        document.getElementById("edit-lesson-folder-label").innerText = currentFolderData.current_rel_path || "ראשי (שרת הישיבה)";
    } else if (activeCardIndex !== null && currentFolderData) {
        document.getElementById(`dest-path-${activeCardIndex}`).value = currentFolderData.current_full_path;
        document.getElementById(`folder-label-${activeCardIndex}`).innerText = currentFolderData.current_rel_path || "ראשי (שורש)";
    }
    closeFolderModal();
}

async function createNewFolderInCurrentDir() {
    const input = document.getElementById("new-folder-input");
    const newName = input.value.trim();
    if (!newName) {
        alert("אנא הזן שם לתיקייה החדשה");
        return;
    }
    if (!currentFolderData) return;

    try {
        const form = new FormData();
        form.append("base_folder", currentFolderData.current_full_path);
        form.append("new_folder_name", newName);

        const res = await fetch("/api/folders/create", { method: "POST", body: form });
        const data = await res.json();
        if (data.status === "success") {
            input.value = "";
            await fetchFolderContent(currentFolderData.current_full_path);
            alert(`✓ התיקייה '${newName}' נוצרה בהצלחה!`);
        } else {
            alert(data.message || "שגיאה ביצירת התיקייה");
        }
    } catch (e) {
        alert("שגיאת תקשורת: " + e.message);
    }
}

// Classify and Move Lesson
async function classifyLesson(index, encodedFilename, encodedSourcePath) {
    const filename = decodeURIComponent(encodedFilename);
    const sourcePath = encodedSourcePath ? decodeURIComponent(encodedSourcePath) : "";
    const rabbi = document.getElementById(`rabbi-${index}`).value.trim();
    const topic = document.getElementById(`topic-${index}`).value.trim();
    const hebrewDate = document.getElementById(`date-${index}`).value.trim();
    const destFolder = document.getElementById(`dest-path-${index}`).value.trim();

    if (!rabbi) {
        alert("אנא הזן את שם הרב");
        document.getElementById(`rabbi-${index}`).focus();
        return;
    }
    if (!destFolder) {
        alert("אנא בחר תיקיית יעד בשרת");
        openFolderExplorer(index);
        return;
    }

    const card = document.getElementById(`card-${index}`);
    card.style.opacity = "0.5";
    card.style.pointerEvents = "none";

    // Unload audio to close file descriptor on server before moving
    const audio = document.getElementById(`audio-${index}`);
    if (audio) {
        audio.pause();
        audio.removeAttribute("src");
        audio.load();
    }
    if (currentAudio === audio) {
        currentAudio = null;
        currentPlayBtn = null;
    }

    try {
        const form = new FormData();
        form.append("filename", filename);
        if (sourcePath) {
            form.append("source_path", sourcePath);
        }
        form.append("rabbi_name", rabbi);
        form.append("lesson_topic", topic);
        form.append("hebrew_date", hebrewDate);
        form.append("destination_folder", destFolder);

        const res = await fetch("/api/lessons/classify", { method: "POST", body: form });
        const data = await res.json();

        if (data.status === "success") {
            card.remove();
            pendingLessons.splice(index, 1);
            document.getElementById("pending-count").innerText = pendingLessons.length;
            renderPendingFolders();
            if (pendingLessons.length === 0) {
                renderPendingLessons();
            }
            alert(`✓ השיעור סווג והועבר בהצלחה לתיקיית הקבע:\n${data.filename}`);
        } else {
            alert(data.detail || "שגיאה בסיווג השיעור");
            card.style.opacity = "1";
            card.style.pointerEvents = "auto";
        }
    } catch (e) {
        alert("שגיאת תקשורת: " + e.message);
        card.style.opacity = "1";
        card.style.pointerEvents = "auto";
    }
}

// Load All Notes (Tab 2)
async function loadNotes() {
    try {
        const res = await fetch("/api/notes/all");
        const data = await res.json();
        allNotes = data.notes || [];
        const openNotes = allNotes.filter(n => n.status === "open");
        document.getElementById("notes-count").innerText = openNotes.length;
        renderAllNotes();
    } catch (e) {
        console.error("Error loading notes:", e);
    }
}

function getNoteTimeGroup(dateStr) {
    if (!dateStr) return "לא ידוע";
    const noteDate = new Date(dateStr.replace(" ", "T"));
    const today = new Date();
    today.setHours(0,0,0,0);
    
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    const lastWeek = new Date(today);
    lastWeek.setDate(lastWeek.getDate() - 7);
    
    const noteDay = new Date(noteDate);
    noteDay.setHours(0,0,0,0);

    if (noteDay.getTime() === today.getTime()) return "היום";
    if (noteDay.getTime() === yesterday.getTime()) return "אתמול";
    if (noteDay.getTime() > lastWeek.getTime()) return "השבוע";
    return "מוקדם יותר";
}

function renderAllNotes() {
    const list = document.getElementById("notes-list");
    if (allNotes.length === 0) {
        list.innerHTML = `<div class="empty-state"><div class="icon">📬</div><h3>אין הערות חדשות מתלמידים</h3></div>`;
        return;
    }

    const groups = { "היום": [], "אתמול": [], "השבוע": [], "מוקדם יותר": [], "לא ידוע": [] };
    
    allNotes.forEach(note => {
        const group = getNoteTimeGroup(note.created_at);
        groups[group].push(note);
    });

    let html = "";
    for (const [groupName, notes] of Object.entries(groups)) {
        if (notes.length === 0) continue;
        
        html += `<div style="font-weight: 600; color: #475569; margin: 1.5rem 0 0.5rem 0; padding-bottom: 0.3rem; border-bottom: 1px solid #e2e8f0; font-size: 1.1rem;">${groupName}</div>`;
        
        html += notes.map(note => `
            <div class="lesson-card" style="${note.status === 'resolved' ? 'opacity: 0.65; background-color: #f8fafc;' : ''}">
                <div class="card-header">
                    <div>
                        <span class="badge ${note.status === 'open' ? 'badge-alert' : 'badge-hebrew-date'}">${note.status === 'open' ? 'פתוחה' : 'טופלה'}</span>
                        <strong style="margin-right: 0.5rem; direction: ltr; unicode-bidi: isolate; display: inline-block;"><bdi>${escapeHtml(note.filename)}</bdi></strong>
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.4rem;" title="${escapeHtml(note.created_at || '')}">
                        <span class="badge badge-hebrew-date">${escapeHtml(getNoteHebrewDate(note) || formatNoteDateDisplay(note))}</span>
                        <span class="badge badge-time">${escapeHtml(getNoteTime(note))}</span>
                    </div>
                </div>
                <div style="margin: 0.75rem 0;">
                    <p><strong>פירוט:</strong> ${escapeHtml(note.description)}</p>
                    <p style="font-size: 0.85rem; color: var(--text-muted);"><strong>נשלח ע"י:</strong> ${escapeHtml(note.student_name)}</p>
                </div>
                <div class="note-actions">
                    ${note.status === 'open' ? `
                        <button class="btn btn-primary btn-sm" onclick="openEditLessonModal('${encodeURIComponent(note.filename).replace(/'/g, '%27')}', ${note.id})">✏️ ערוך שיעור</button>
                        <button class="btn btn-outline btn-sm" onclick="resolveNote(${note.id})">✓ סמן כטופל</button>
                    ` : `
                        <button class="btn btn-sm" disabled style="opacity: 0.5; cursor: not-allowed; background: #e2e8f0; color: #94a3b8; border: 1px solid #cbd5e1;" title="ההערה כבר סומנה כטופלה">✏️ ערוך שיעור (טופל)</button>
                    `}
                </div>
            </div>
        `).join("");
    }

    list.innerHTML = html;
}

async function resolveNote(noteId) {
    try {
        const form = new FormData();
        form.append("note_id", noteId);
        form.append("status", "resolved");
        await fetch("/api/notes/status", { method: "POST", body: form });

        // 1. Remove banner from lesson card in DOM immediately with smooth animation
        const banner = document.getElementById(`note-banner-${noteId}`);
        if (banner) {
            banner.style.transition = "all 0.25s ease";
            banner.style.opacity = "0";
            banner.style.maxHeight = "0";
            banner.style.margin = "0";
            banner.style.padding = "0";
            banner.style.overflow = "hidden";
            setTimeout(() => banner.remove(), 260);
        }

        // 2. Remove the note from pendingLessons in memory
        pendingLessons.forEach(lesson => {
            if (lesson.notes && lesson.notes.length > 0) {
                lesson.notes = lesson.notes.filter(n => n.id !== noteId);
            }
        });

        // 3. Refresh notes tab and badge count
        await loadNotes();
    } catch (e) {
        console.error("Error resolving note:", e);
        alert("שגיאה בעדכון ההערה: " + e.message);
    }
}

function getNoteHebrewDate(note) {
    if (!note) return "";
    if (note.hebrew_date) return note.hebrew_date;
    if (note.created_at) {
        try {
            const dt = new Date(note.created_at.replace(' ', 'T'));
            if (!isNaN(dt.getTime())) {
                return new Intl.DateTimeFormat('he-u-ca-hebrew', { day: 'numeric', month: 'long', year: 'numeric' }).format(dt);
            }
        } catch (e) {}
    }
    return "";
}

function getNoteTime(note) {
    if (!note) return "";
    const timePart = note.created_time || (note.created_at ? note.created_at.split(' ')[1] : '');
    return timePart ? (timePart.length === 8 ? timePart.substring(0, 5) : timePart) : '';
}

function formatNoteDateDisplay(note) {
    if (!note) return "";
    const heb = getNoteHebrewDate(note);
    const timeStr = getNoteTime(note);
    if (heb) {
        return timeStr ? `${heb} | ${timeStr}` : heb;
    }
    return note.created_at || "";
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Delete Lesson with active confirmation
async function deleteLesson(index, encodedFilename, encodedSourcePath) {
    const filename = decodeURIComponent(encodedFilename);
    const sourcePath = encodedSourcePath ? decodeURIComponent(encodedSourcePath) : "";
    const confirmMsg = `האם אתה בטוח שברצונך למחוק לצמיתות את ההקלטה?\n\n"${filename}"\n\nפעולה זו אינה ניתנת לביטול!`;
    if (!confirm(confirmMsg)) {
        return;
    }

    const card = document.getElementById(`card-${index}`);
    if (card) {
        card.style.opacity = "0.4";
        card.style.pointerEvents = "none";
    }

    // Unload audio to close file descriptor on server before deleting
    const audio = document.getElementById(`audio-${index}`);
    if (audio) {
        audio.pause();
        audio.removeAttribute("src");
        audio.load();
    }
    if (currentAudio === audio) {
        currentAudio = null;
        currentPlayBtn = null;
    }

    try {
        const form = new FormData();
        form.append("filename", filename);
        if (sourcePath) {
            form.append("source_path", sourcePath);
        }

        const res = await fetch("/api/lessons/delete", { method: "POST", body: form });
        const data = await res.json();

        if (data.status === "success") {
            if (card) card.remove();
            pendingLessons.splice(index, 1);
            document.getElementById("pending-count").innerText = pendingLessons.length;
            renderPendingFolders();
            if (pendingLessons.length === 0) {
                renderPendingLessons();
            }
            alert(`✓ הקובץ נמחק בהצלחה:\n${filename}`);
        } else {
            alert(data.message || data.detail || "שגיאה במחיקת הקובץ");
            if (card) {
                card.style.opacity = "1";
                card.style.pointerEvents = "auto";
            }
        }
    } catch (e) {
        alert("שגיאת תקשורת: " + e.message);
        if (card) {
            card.style.opacity = "1";
            card.style.pointerEvents = "auto";
        }
    }
}

// Open Edit Lesson Modal from Note
async function openEditLessonModal(encodedFilename, noteId) {
    const filename = decodeURIComponent(encodedFilename);
    const note = allNotes.find(n => n.id === noteId);

    if (note && note.status !== "open") {
        alert("הערה זו כבר סומנה כטופלה ולא ניתן לערוך את השיעור.");
        return;
    }

    if (note) {
        document.getElementById("edit-modal-student-name").innerText = note.student_name || "תלמיד אנונימי";
        document.getElementById("edit-modal-note-desc").innerText = note.description || "";
        document.getElementById("edit-modal-note-meta").innerText = `נשלח בתאריך: ${formatNoteDateDisplay(note)}`;
    }
    document.getElementById("edit-lesson-note-id").value = noteId || "";

    try {
        const res = await fetch(`/api/lessons/details_for_edit?filename=${encodeURIComponent(filename)}&note_id=${noteId || ''}`);
        const data = await res.json();

        if (!data.found) {
            alert(`⚠️ הקובץ '${filename}' לא נמצא כרגע בשרת (ייתכן שכבר הועבר או נמחק).`);
            return;
        }

        document.getElementById("edit-lesson-source-path").value = data.full_path;
        document.getElementById("edit-lesson-filename-display").innerText = data.filename;
        document.getElementById("edit-lesson-rabbi").value = data.rabbi || "";
        document.getElementById("edit-lesson-topic").value = data.topic || "";
        document.getElementById("edit-lesson-date").value = data.hebrew_date || "";
        document.getElementById("edit-lesson-dest-path").value = data.parent_folder || "";
        document.getElementById("edit-lesson-folder-label").innerText = data.parent_folder_rel || "בחר תיקייה...";

        const audio = document.getElementById("audio-edit");
        audio.src = `/api/audio/stream?filename=${encodeURIComponent(data.full_path).replace(/'/g, '%27')}`;
        audio.load();

        document.getElementById("edit-lesson-modal").classList.add("open");
    } catch (e) {
        alert("שגיאה בטעינת פרטי הקובץ: " + e.message);
    }
}

function closeEditLessonModal() {
    const audio = document.getElementById("audio-edit");
    if (audio) {
        audio.pause();
    }
    const playBtn = document.getElementById("play-btn-edit");
    if (playBtn) playBtn.innerText = "▶";
    document.getElementById("edit-lesson-modal").classList.remove("open");
}

async function saveEditedLesson() {
    const sourcePath = document.getElementById("edit-lesson-source-path").value;
    const noteId = document.getElementById("edit-lesson-note-id").value;
    const rabbi = document.getElementById("edit-lesson-rabbi").value.trim();
    const topic = document.getElementById("edit-lesson-topic").value.trim();
    const hebrewDate = document.getElementById("edit-lesson-date").value.trim();
    const destFolder = document.getElementById("edit-lesson-dest-path").value.trim();

    if (!rabbi) {
        alert("אנא הזן את שם הרב");
        document.getElementById("edit-lesson-rabbi").focus();
        return;
    }
    if (!destFolder) {
        alert("אנא בחר תיקיית יעד בשרת הישיבה");
        openFolderExplorer("edit-modal");
        return;
    }

    const saveBtn = document.getElementById("edit-lesson-save-btn");
    saveBtn.disabled = true;
    saveBtn.innerText = "שומר...";

    try {
        const form = new FormData();
        form.append("source_path", sourcePath);
        form.append("rabbi_name", rabbi);
        form.append("lesson_topic", topic);
        form.append("hebrew_date", hebrewDate);
        form.append("destination_folder", destFolder);
        if (noteId) form.append("note_id", noteId);

        const res = await fetch("/api/lessons/update", { method: "POST", body: form });
        const data = await res.json();

        if (data.status === "success") {
            closeEditLessonModal();
            await loadNotes();
            await loadPendingLessons();
            alert(`✓ השיעור עודכן בהצלחה!\nשם חדש: ${data.filename}`);
        } else {
            alert(data.message || data.detail || "שגיאה בעדכון השיעור");
        }
    } catch (e) {
        alert("שגיאת תקשורת: " + e.message);
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerText = "💾 שמור שינויים וסמן כטופל";
    }
}
