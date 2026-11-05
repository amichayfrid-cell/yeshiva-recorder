// State
let pendingLessons = [];
let currentPendingSource = null;
let allNotes = [];
let activeCardIndex = null;
let currentFolderData = null;
let currentAudio = null;
let currentPlayBtn = null;
let highlightedFolderIndex = 0;
let currentSortOrder = localStorage.getItem("yeshiva_sort_order") || "newest";

// Initialization
document.addEventListener("DOMContentLoaded", () => {
    loadPendingLessons();
    loadNotes();
    setupKeyboardListeners();
    makeModalDraggable("folder-modal");
    makeModalDraggable("edit-lesson-modal");
    syncSortOrderUI();
});

// ==========================================
// Floating Draggable Modals Mechanism
// ==========================================
function makeModalDraggable(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    const box = modal.querySelector(".modal-box");
    const header = modal.querySelector(".modal-header");
    if (!box || !header) return;

    header.style.cursor = "grab";
    header.setAttribute("title", "לחץ וגרור כדי להזיז את החלון");

    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let currentX = 0;
    let currentY = 0;

    box._resetDrag = function() {
        currentX = 0;
        currentY = 0;
        box.style.transform = "";
    };

    function onPointerDown(e) {
        if (e.target.closest("button, input, select, textarea, a")) return;

        isDragging = true;
        header.style.cursor = "grabbing";
        box.classList.add("is-dragging");

        const pageX = e.type.startsWith("touch") ? e.touches[0].clientX : e.clientX;
        const pageY = e.type.startsWith("touch") ? e.touches[0].clientY : e.clientY;

        startX = pageX - currentX;
        startY = pageY - currentY;

        window.addEventListener("mousemove", onPointerMove);
        window.addEventListener("mouseup", onPointerUp);
        window.addEventListener("touchmove", onPointerMove, { passive: false });
        window.addEventListener("touchend", onPointerUp);
    }

    function onPointerMove(e) {
        if (!isDragging) return;
        if (e.cancelable && e.type === "touchmove") e.preventDefault();

        const pageX = e.type.startsWith("touch") ? e.touches[0].clientX : e.clientX;
        const pageY = e.type.startsWith("touch") ? e.touches[0].clientY : e.clientY;

        let newX = pageX - startX;
        let newY = pageY - startY;

        const boundX = Math.max(100, (window.innerWidth / 2) - 60);
        const boundY = Math.max(60, (window.innerHeight / 2) - 40);

        newX = Math.max(-boundX, Math.min(boundX, newX));
        newY = Math.max(-boundY, Math.min(boundY, newY));

        currentX = newX;
        currentY = newY;
        box.style.transform = `translate3d(${newX}px, ${newY}px, 0)`;
    }

    function onPointerUp() {
        if (!isDragging) return;
        isDragging = false;
        header.style.cursor = "grab";
        box.classList.remove("is-dragging");

        window.removeEventListener("mousemove", onPointerMove);
        window.removeEventListener("mouseup", onPointerUp);
        window.removeEventListener("touchmove", onPointerMove);
        window.removeEventListener("touchend", onPointerUp);
    }

    header.addEventListener("mousedown", onPointerDown);
    header.addEventListener("touchstart", onPointerDown, { passive: true });
}


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

// ==========================================
// Sorting Mechanism (Newest vs Oldest)
// ==========================================
function sortPendingLessons() {
    pendingLessons.sort((a, b) => {
        const timeA = (a.mtime && a.mtime > 0) ? a.mtime : 0;
        const timeB = (b.mtime && b.mtime > 0) ? b.mtime : 0;
        if (timeA !== timeB) {
            return currentSortOrder === "oldest" ? (timeA - timeB) : (timeB - timeA);
        }
        return currentSortOrder === "oldest" 
            ? a.filename.localeCompare(b.filename)
            : b.filename.localeCompare(a.filename);
    });
}

function setSortOrder(order) {
    currentSortOrder = order;
    try {
        localStorage.setItem("yeshiva_sort_order", order);
    } catch (e) {}

    syncSortOrderUI();
    sortPendingLessons();
    renderPendingLessons();
}

function syncSortOrderUI() {
    const btnNewest = document.getElementById("sort-newest-btn");
    const btnOldest = document.getElementById("sort-oldest-btn");
    if (btnNewest) btnNewest.classList.toggle("active", currentSortOrder === "newest");
    if (btnOldest) btnOldest.classList.toggle("active", currentSortOrder === "oldest");
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
        sortPendingLessons();

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
    syncSortOrderUI();
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

    filtered.sort((a, b) => {
        const timeA = (a.mtime && a.mtime > 0) ? a.mtime : 0;
        const timeB = (b.mtime && b.mtime > 0) ? b.mtime : 0;
        if (timeA !== timeB) {
            return currentSortOrder === "oldest" ? (timeA - timeB) : (timeB - timeA);
        }
        return currentSortOrder === "oldest" 
            ? a.filename.localeCompare(b.filename)
            : b.filename.localeCompare(a.filename);
    });

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
            : `<span class="badge badge-source-recorder" title="לחץ לשינוי שם המקלט (למשל: מקלט 4)" onclick="editRecorderName('${encodeURIComponent(lesson.filename).replace(/'/g, '%27')}', '${escapeHtml(lesson.source_label || "מקלט שמע")}')" style="cursor: pointer; user-select: none;">🎙️ ${escapeHtml(lesson.source_label || "מקלט שמע")}</span>`;

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
                        <input type="text" class="input-text" id="rabbi-${index}" placeholder="למשל: הרב אורי" required onkeydown="handleLessonCardKeyDown(event, ${index}, 'rabbi')">
                    </div>
                    <div class="form-field">
                        <label>נושא / שם השיעור:</label>
                        <input type="text" class="input-text" id="topic-${index}" placeholder="למשל: פרשת כי תצא" onkeydown="handleLessonCardKeyDown(event, ${index}, 'topic')">
                    </div>
                    <div class="form-field">
                        <label>תאריך עברי:</label>
                        <input type="text" class="input-text" id="date-${index}" value="${escapeHtml(lesson.hebrew_date)}" onkeydown="handleLessonCardKeyDown(event, ${index}, 'date')">
                    </div>
                    <div class="form-field">
                        <label>תיקיית יעד בשרת:</label>
                        <div class="folder-picker-wrap">
                            <button type="button" class="folder-select-btn" id="folder-btn-${index}" onclick="openFolderExplorer('${index}')" onkeydown="handleLessonCardKeyDown(event, ${index}, 'folder')">
                                <span id="folder-label-${index}">בחר תיקיית יעד...</span>
                                <span>📁 ▾</span>
                            </button>
                            <input type="hidden" id="dest-path-${index}">
                        </div>
                    </div>
                    <div style="display: flex; gap: 0.5rem;">
                        <button id="save-btn-${index}" class="btn btn-success" onclick="classifyLesson('${index}', '${encodeURIComponent(lesson.filename).replace(/'/g, '%27')}', '${encodeURIComponent(lesson.full_path || '').replace(/'/g, '%27')}')" onkeydown="handleLessonCardKeyDown(event, ${index}, 'save')">
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
    const listContainer = document.getElementById("modal-folders-list");
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

    if (localFiltered.length > 0) {
        renderFolderSearchResults(localFiltered, q, true, true);
    } else {
        if (listContainer) {
            listContainer.innerHTML = `
                <div style="text-align: center; padding: 2.5rem 1rem; color: var(--text-muted);">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔍</div>
                    <div style="font-weight: 600; font-size: 1rem; color: var(--text-main); margin-bottom: 0.25rem;">
                        מחפש "${escapeHtml(q)}" בכל תת-התיקיות בשרת...
                    </div>
                </div>
            `;
        }
    }

    // 2. Global search across ALL subfolders on the server (debounced 120ms)
    clearTimeout(folderSearchTimer);
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
                renderFolderSearchResults(currentFolderSearchResults, q, false, false);
            }
        } catch (err) {
            console.warn("Folder search failed:", err);
        }
    }, 120);
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

function renderFolderSearchResults(results, query, isLocalOnly = false, isSearchingGlobal = false) {
    const listContainer = document.getElementById("modal-folders-list");
    if (!listContainer) return;

    if (!results || results.length === 0) {
        listContainer.innerHTML = `
            <div style="text-align: center; padding: 2.5rem 1rem; color: var(--text-muted);">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔍</div>
                <div style="font-weight: 600; font-size: 1rem; color: var(--text-main); margin-bottom: 0.25rem;">
                    לא נמצאו תת-תיקיות עבור "${escapeHtml(query)}"
                </div>
                <div style="font-size: 0.85rem;">
                    נסה לחפש במילים קצרות יותר (למשל שם הרב או שנתון), או צור תיקייה חדשה למטה
                </div>
            </div>
        `;
        return;
    }

    const countLabel = isSearchingGlobal 
        ? `${results.length} תיקיות בתיקייה זו (מחפש גם בכל תת-התיקיות ברחבי השרת...)`
        : (isLocalOnly ? `${results.length} תיקיות בתיקייה זו` : `${results.length} תת-תיקיות נמצאו בכל רחבי השרת`);

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
    const targetCard = activeCardIndex;

    if (activeCardIndex === "edit-modal") {
        document.getElementById("edit-lesson-dest-path").value = full;
        document.getElementById("edit-lesson-folder-label").innerText = rel || "ראשי (שרת הישיבה)";
        setTimeout(() => document.getElementById("edit-lesson-save-btn")?.focus(), 60);
    } else if (activeCardIndex !== null) {
        document.getElementById(`dest-path-${activeCardIndex}`).value = full;
        document.getElementById(`folder-label-${activeCardIndex}`).innerText = rel || "ראשי (שורש)";
        setTimeout(() => document.getElementById(`save-btn-${targetCard}`)?.focus(), 60);
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
    handleFolderModalGlobalKeyDown(e);
}

function openFolderExplorer(cardIndex) {
    activeCardIndex = cardIndex;
    clearFolderSearch(false);
    highlightedFolderIndex = 0;
    highlightedSearchResultIndex = 0;
    const box = document.querySelector("#folder-modal .modal-box");
    if (box && box._resetDrag) box._resetDrag();
    const currentStoredPath = getStoredFolderPath();
    fetchFolderContent(currentStoredPath);
    document.getElementById("folder-modal").classList.add("open");

    setTimeout(() => {
        const input = document.getElementById("modal-folder-search-input");
        if (input) {
            input.focus();
            input.select();
        }
    }, 60);
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
        const isWeeklyFolder = (
            (currentFolderData.current_name && currentFolderData.current_name.trim() === "שיעורי השבוע") ||
            (currentFolderData.current_rel_path && (
                currentFolderData.current_rel_path.trim() === "שיעורי השבוע" ||
                currentFolderData.current_rel_path.startsWith("שיעורי השבוע/") ||
                currentFolderData.current_rel_path.startsWith("שיעורי השבוע\\")
            )) ||
            (currentFolderData.current_full_path && (
                currentFolderData.current_full_path.endsWith("/שיעורי השבוע") ||
                currentFolderData.current_full_path.endsWith("\\שיעורי השבוע") ||
                currentFolderData.current_full_path.includes("/שיעורי השבוע/") ||
                currentFolderData.current_full_path.includes("\\שיעורי השבוע\\")
            ))
        );

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
                        const editBtnHtml = isWeeklyFolder ? "" : `
                            <button type="button" 
                                    class="btn-edit-existing-lesson" 
                                    onclick="openEditFromExplorer('${encodeURIComponent(name).replace(/'/g, "%27")}', this)"
                                    title="ערוך שיעור זה">
                                ✏️ ערוך
                            </button>
                        `;
                        return `
                            <div class="existing-lesson-item">
                                <div class="existing-lesson-main">
                                    <span class="existing-lesson-icon">🎵</span>
                                    <div class="existing-lesson-info">
                                        <div class="existing-lesson-name" title="${escapeHtml(name)}">${escapeHtml(cleanName)}</div>
                                        <span class="existing-lesson-ext">${ext}</span>
                                    </div>
                                </div>
                                <div class="existing-lesson-actions">
                                    ${editBtnHtml}
                                    <button type="button" 
                                            class="btn-preview-audio" 
                                            id="preview-btn-${i}"
                                            onclick="toggleModalAudioPreview('${encodeURIComponent(name).replace(/'/g, "%27")}', 'preview-btn-${i}')"
                                            title="השמע שיעור">
                                        ▶ השמע
                                    </button>
                                </div>
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

// ==========================================
// Full Keyboard Navigation & Accessibility Engine
// ==========================================

function handleFolderModalGlobalKeyDown(e) {
    const searchInput = document.getElementById("modal-folder-search-input");
    const newFolderInput = document.getElementById("new-folder-input");
    const isSearchFocused = (document.activeElement === searchInput);
    const isNewFolderFocused = (document.activeElement === newFolderInput);

    // Escape: clear search if has text, or close modal
    if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        if (searchInput && searchInput.value.trim().length > 0) {
            clearFolderSearch(true);
            searchInput.focus();
        } else {
            closeFolderModal();
        }
        return;
    }

    // Ctrl + Enter: Instant Selection Confirmation from anywhere!
    if (e.ctrlKey && e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        if (currentFolderSearchResults && currentFolderSearchResults.length > 0) {
            const item = currentFolderSearchResults[highlightedSearchResultIndex];
            if (item) {
                confirmDirectFolderSelection(encodeURIComponent(item.full_path), encodeURIComponent(item.rel_path || item.name));
                return;
            }
        }
        confirmCurrentFolderSelection();
        return;
    }

    // If user is typing in new folder input:
    if (isNewFolderFocused) {
        if (e.key === "Enter") {
            e.preventDefault();
            createNewFolderInCurrentDir();
        }
        return;
    }

    const isSearching = (currentFolderSearchResults !== null);
    const subfolders = (currentFolderData && currentFolderData.subfolders)
        ? currentFolderData.subfolders.filter(s => !s.name.includes("הגברת החירות"))
        : [];

    // ArrowDown
    if (e.key === "ArrowDown") {
        e.preventDefault();
        if (isSearching && currentFolderSearchResults && currentFolderSearchResults.length > 0) {
            highlightedSearchResultIndex = (highlightedSearchResultIndex + 1) % currentFolderSearchResults.length;
            updateSearchHighlightedUI();
            const el = document.getElementById(`search-res-${highlightedSearchResultIndex}`);
            if (el) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
        } else if (!isSearching && subfolders.length > 0) {
            highlightedFolderIndex = (highlightedFolderIndex + 1) % subfolders.length;
            updateHighlightedUI();
            scrollHighlightedIntoView();
        }
        return;
    }

    // ArrowUp
    if (e.key === "ArrowUp") {
        e.preventDefault();
        if (isSearching && currentFolderSearchResults && currentFolderSearchResults.length > 0) {
            highlightedSearchResultIndex = (highlightedSearchResultIndex - 1 + currentFolderSearchResults.length) % currentFolderSearchResults.length;
            updateSearchHighlightedUI();
            const el = document.getElementById(`search-res-${highlightedSearchResultIndex}`);
            if (el) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
        } else if (!isSearching && subfolders.length > 0) {
            highlightedFolderIndex = (highlightedFolderIndex - 1 + subfolders.length) % subfolders.length;
            updateHighlightedUI();
            scrollHighlightedIntoView();
        }
        return;
    }

    // Enter
    if (e.key === "Enter") {
        e.preventDefault();
        if (isSearching && currentFolderSearchResults && currentFolderSearchResults.length > 0) {
            const item = currentFolderSearchResults[highlightedSearchResultIndex];
            if (item) {
                enterSearchResultFolder(encodeURIComponent(item.full_path));
            }
        } else if (!isSearching) {
            if (subfolders.length > 0) {
                handleItemClick(highlightedFolderIndex);
            } else {
                confirmCurrentFolderSelection();
            }
        }
        return;
    }

    // ArrowLeft (In RTL Hebrew, Left arrow moves forward / enters folder)
    if (e.key === "ArrowLeft") {
        if (isSearchFocused && searchInput.selectionStart !== searchInput.value.length) {
            return;
        }
        e.preventDefault();
        if (isSearching && currentFolderSearchResults && currentFolderSearchResults.length > 0) {
            const item = currentFolderSearchResults[highlightedSearchResultIndex];
            if (item) enterSearchResultFolder(encodeURIComponent(item.full_path));
        } else if (!isSearching && subfolders.length > 0) {
            handleItemClick(highlightedFolderIndex);
        }
        return;
    }

    // ArrowRight (In RTL Hebrew, Right arrow goes backward / up to parent)
    if (e.key === "ArrowRight") {
        if (isSearchFocused && (searchInput.value.length > 0 && searchInput.selectionStart > 0)) {
            return;
        }
        e.preventDefault();
        if (currentFolderData && currentFolderData.parent_path) {
            fetchFolderContent(currentFolderData.parent_path);
        }
        return;
    }

    // Backspace: go back if search input is empty or focus not in input
    if (e.key === "Backspace") {
        if (!isSearchFocused || searchInput.value === "") {
            e.preventDefault();
            if (currentFolderData && currentFolderData.parent_path) {
                fetchFolderContent(currentFolderData.parent_path);
            }
        }
    }
}

function handleLessonCardKeyDown(e, index, field) {
    if (e.key === "Enter") {
        if (e.ctrlKey) {
            e.preventDefault();
            const saveBtn = document.getElementById(`save-btn-${index}`);
            if (saveBtn) saveBtn.click();
            return;
        }

        e.preventDefault();
        if (field === "rabbi") {
            const topicInput = document.getElementById(`topic-${index}`);
            if (topicInput) {
                topicInput.focus();
                topicInput.select();
            }
        } else if (field === "topic") {
            const dateInput = document.getElementById(`date-${index}`);
            if (dateInput) {
                dateInput.focus();
                dateInput.select();
            }
        } else if (field === "date") {
            const destPath = document.getElementById(`dest-path-${index}`)?.value;
            if (destPath) {
                const saveBtn = document.getElementById(`save-btn-${index}`);
                if (saveBtn) saveBtn.focus();
            } else {
                openFolderExplorer(index);
            }
        } else if (field === "folder") {
            openFolderExplorer(index);
        } else if (field === "save") {
            const saveBtn = document.getElementById(`save-btn-${index}`);
            if (saveBtn) saveBtn.click();
        }
    } else if (e.key === "ArrowDown") {
        if (e.altKey) {
            e.preventDefault();
            focusLessonCard(index + 1);
        } else if (e.target.tagName === "INPUT") {
            const input = e.target;
            if (input.selectionStart === input.value.length) {
                e.preventDefault();
                if (field === "rabbi") {
                    const el = document.getElementById(`topic-${index}`);
                    if (el) { el.focus(); el.select(); }
                } else if (field === "topic") {
                    const el = document.getElementById(`date-${index}`);
                    if (el) { el.focus(); el.select(); }
                } else if (field === "date") {
                    document.getElementById(`folder-btn-${index}`)?.focus();
                }
            }
        }
    } else if (e.key === "ArrowUp") {
        if (e.altKey) {
            e.preventDefault();
            focusLessonCard(index - 1);
        } else if (e.target.tagName === "INPUT") {
            const input = e.target;
            if (input.selectionStart === 0 && input.selectionEnd === 0) {
                e.preventDefault();
                if (field === "topic") {
                    const el = document.getElementById(`rabbi-${index}`);
                    if (el) { el.focus(); el.select(); }
                } else if (field === "date") {
                    const el = document.getElementById(`topic-${index}`);
                    if (el) { el.focus(); el.select(); }
                }
            }
        }
    }
}

function focusLessonCard(index) {
    const card = document.getElementById(`card-${index}`);
    if (!card) return;
    card.scrollIntoView({ block: "center", behavior: "smooth" });
    const rabbiInput = document.getElementById(`rabbi-${index}`);
    if (rabbiInput) {
        rabbiInput.focus();
        rabbiInput.select();
    }
}

function getActiveCardIndex() {
    const activeEl = document.activeElement;
    if (!activeEl) return null;
    const card = activeEl.closest(".lesson-card");
    if (!card) return null;
    const match = card.id.match(/^card-(\d+)$/);
    return match ? parseInt(match[1], 10) : null;
}

function navigateCardDelta(delta) {
    const cards = Array.from(document.querySelectorAll(".lesson-card"));
    if (cards.length === 0) return;
    const currentActive = getActiveCardIndex();
    if (currentActive === null) {
        focusLessonCard(0);
        return;
    }
    const currentCardIdx = cards.findIndex(c => c.id === `card-${currentActive}`);
    const nextIdx = currentCardIdx + delta;
    if (nextIdx >= 0 && nextIdx < cards.length) {
        const nextIdMatch = cards[nextIdx].id.match(/^card-(\d+)$/);
        if (nextIdMatch) {
            focusLessonCard(parseInt(nextIdMatch[1], 10));
        }
    }
}

function handleEditModalKeyDown(e, field) {
    if (e.key === "Enter") {
        if (e.ctrlKey) {
            e.preventDefault();
            saveEditedLesson();
            return;
        }
        e.preventDefault();
        if (field === "rabbi") {
            const topicInput = document.getElementById("edit-lesson-topic");
            if (topicInput) {
                topicInput.focus();
                topicInput.select();
            }
        } else if (field === "topic") {
            const dateInput = document.getElementById("edit-lesson-date");
            if (dateInput) {
                dateInput.focus();
                dateInput.select();
            }
        } else if (field === "date") {
            const dest = document.getElementById("edit-lesson-dest-path")?.value;
            if (dest) {
                document.getElementById("edit-lesson-save-btn")?.focus();
            } else {
                openFolderExplorer("edit-modal");
            }
        } else if (field === "folder") {
            openFolderExplorer("edit-modal");
        } else if (field === "save") {
            saveEditedLesson();
        }
    }
}

// Global Keyboard Navigation Listener
function setupKeyboardListeners() {
    window.addEventListener("keydown", (e) => {
        const folderModal = document.getElementById("folder-modal");
        const editModal = document.getElementById("edit-lesson-modal");

        // 1. If Folder Modal is Open
        if (folderModal && folderModal.classList.contains("open")) {
            handleFolderModalGlobalKeyDown(e);
            return;
        }

        // 2. If Edit Lesson Modal is Open
        if (editModal && editModal.classList.contains("open")) {
            if (e.key === "Escape") {
                e.preventDefault();
                closeEditLessonModal();
                return;
            }
            if (e.ctrlKey && e.key === "Enter") {
                e.preventDefault();
                saveEditedLesson();
                return;
            }
            return;
        }

        // 3. Main Dashboard Navigation
        // Alt + ArrowDown / PageDown: Next card
        if ((e.altKey && e.key === "ArrowDown") || e.key === "PageDown") {
            e.preventDefault();
            navigateCardDelta(1);
            return;
        }
        // Alt + ArrowUp / PageUp: Previous card
        if ((e.altKey && e.key === "ArrowUp") || e.key === "PageUp") {
            e.preventDefault();
            navigateCardDelta(-1);
            return;
        }

        // Alt + P: Audio play/pause for active card
        if (e.altKey && (e.key === "p" || e.key === "P")) {
            e.preventDefault();
            const activeCard = getActiveCardIndex();
            if (activeCard !== null) {
                togglePlay(activeCard);
            }
            return;
        }
    });
}

function fetchFolderByRelativePath(relPath) {
    fetchFolderContent(relPath);
}

function confirmCurrentFolderSelection() {
    const targetCard = activeCardIndex;
    if (activeCardIndex === "edit-modal" && currentFolderData) {
        document.getElementById("edit-lesson-dest-path").value = currentFolderData.current_full_path;
        document.getElementById("edit-lesson-folder-label").innerText = currentFolderData.current_rel_path || "ראשי (שרת הישיבה)";
        setTimeout(() => document.getElementById("edit-lesson-save-btn")?.focus(), 60);
    } else if (activeCardIndex !== null && currentFolderData) {
        document.getElementById(`dest-path-${activeCardIndex}`).value = currentFolderData.current_full_path;
        document.getElementById(`folder-label-${activeCardIndex}`).innerText = currentFolderData.current_rel_path || "ראשי (שורש)";
        setTimeout(() => document.getElementById(`save-btn-${targetCard}`)?.focus(), 60);
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
            renderPendingLessons();
            alert(`✓ השיעור סווג והועבר בהצלחה לתיקיית הקבע:\n${data.filename}`);
            const nextIdx = Math.min(index, pendingLessons.length - 1);
            if (nextIdx >= 0) {
                setTimeout(() => focusLessonCard(nextIdx), 60);
            }
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
                        <button class="btn btn-primary btn-sm" onclick="openEditLessonModal('${encodeURIComponent(note.filename).replace(/'/g, '%27')}', ${note.id}, this)">✏️ ערוך שיעור</button>
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

// Edit Recorder Name directly from badge
async function editRecorderName(encodedFilename, currentLabel) {
    const filename = decodeURIComponent(encodedFilename);
    const newName = prompt("הזן שם עבור מקלט זה (למשל: מקלט 4, מקלט א, בית מדרש):", currentLabel || "מקלט שמע");
    if (!newName || newName.trim() === "" || newName.trim() === currentLabel) return;

    try {
        const form = new FormData();
        form.append("filename", filename);
        form.append("recorder_label", newName.trim());
        const res = await fetch("/api/lessons/set_recorder_source", { method: "POST", body: form });
        const data = await res.json();
        if (data.status === "success") {
            const lesson = pendingLessons.find(l => l.filename === filename);
            if (lesson) {
                lesson.source_label = data.recorder_label;
                renderPendingLessons();
            }
        }
    } catch (e) {
        alert("שגיאה בעדכון שם המקלט: " + e.message);
    }
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

let editOpenedFromExplorer = false;

function normalizeHebrewQuotes(s) {
    if (!s) return "";
    return s.replace(/['׳’‘`]/g, "'").replace(/["״”“]|''/g, '"').trim().toLowerCase();
}

async function openEditFromExplorer(encodedFilename, btnElement = null) {
    const filename = decodeURIComponent(encodedFilename);
    if (!currentFolderData) return;

    stopModalAudioPreview();

    // Check if there is an open note for this file with Hebrew quote tolerance
    const normFile = normalizeHebrewQuotes(filename);
    const matchingNote = (allNotes || []).find(n => {
        const nBase = (n.filename || "").replace(/\\/g, "/").split("/").pop();
        return normalizeHebrewQuotes(nBase) === normFile && n.status === "open";
    });

    const noteId = matchingNote ? matchingNote.id : null;
    editOpenedFromExplorer = true;

    // Temporarily hide folder modal so edit modal is cleanly visible
    document.getElementById("folder-modal").classList.remove("open");

    const folderPath = currentFolderData.current_full_path || "";
    await openEditLessonModal(encodedFilename, noteId, btnElement, folderPath);
}

// Open Edit Lesson Modal (from Note or Folder Explorer)
async function openEditLessonModal(encodedFilename, noteId, btnElement = null, forcedFolderPath = null) {
    const filename = decodeURIComponent(encodedFilename);
    const note = (allNotes || []).find(n => n.id === noteId);

    if (note && note.status !== "open") {
        alert("הערה זו כבר סומנה כטופלה ולא ניתן לערוך את השיעור.");
        return;
    }

    const noteBanner = document.getElementById("edit-modal-note-banner");
    const modalTitle = document.querySelector("#edit-lesson-modal .modal-header h3");
    const saveBtn = document.getElementById("edit-lesson-save-btn");

    if (note) {
        if (noteBanner) noteBanner.style.display = "flex";
        if (modalTitle) modalTitle.innerText = "✏️ עריכת שיעור ופתרון פנייה";
        if (saveBtn) saveBtn.innerHTML = "💾 שמור שינויים וסמן כטופל";
        document.getElementById("edit-modal-student-name").innerText = note.student_name || "תלמיד אנונימי";
        document.getElementById("edit-modal-note-desc").innerText = note.description || "";
        document.getElementById("edit-modal-note-meta").innerText = `נשלח בתאריך: ${formatNoteDateDisplay(note)}`;
    } else {
        if (noteBanner) noteBanner.style.display = "none";
        if (modalTitle) modalTitle.innerText = "✏️ עריכת שיעור";
        if (saveBtn) saveBtn.innerHTML = "💾 שמור שינויים";
    }
    document.getElementById("edit-lesson-note-id").value = noteId || "";

    let origPath = "";
    let folderPath = forcedFolderPath || "";

    if (forcedFolderPath) {
        origPath = forcedFolderPath + "/" + filename;
    } else if (note && note.original_path) {
        origPath = note.original_path;
    } else if (currentFolderData && currentFolderData.current_full_path) {
        folderPath = currentFolderData.current_full_path;
        origPath = folderPath + "/" + filename;
    }

    let prevBtnHtml = "";
    if (btnElement) {
        prevBtnHtml = btnElement.innerHTML;
        btnElement.innerHTML = "⏳ טוען...";
        btnElement.style.pointerEvents = "none";
    }

    try {
        const queryParams = new URLSearchParams({
            filename: filename,
            note_id: noteId || '',
            original_path: origPath,
            folder_path: folderPath
        });
        const res = await fetch(`/api/lessons/details_for_edit?${queryParams.toString()}`);
        const data = await res.json();

        if (!data.found) {
            alert(`⚠️ הקובץ '${filename}' לא נמצא כרגע בשרת (ייתכן שכבר הועבר או נמחק).`);
            if (editOpenedFromExplorer) {
                editOpenedFromExplorer = false;
                document.getElementById("folder-modal").classList.add("open");
            }
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

        const editBox = document.querySelector("#edit-lesson-modal .modal-box");
        if (editBox && editBox._resetDrag) editBox._resetDrag();
        document.getElementById("edit-lesson-modal").classList.add("open");
    } catch (e) {
        alert("שגיאה בטעינת פרטי הקובץ: " + e.message);
        if (editOpenedFromExplorer) {
            editOpenedFromExplorer = false;
            document.getElementById("folder-modal").classList.add("open");
        }
    } finally {
        if (btnElement) {
            btnElement.innerHTML = prevBtnHtml;
            btnElement.style.pointerEvents = "auto";
        }
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

    if (editOpenedFromExplorer) {
        editOpenedFromExplorer = false;
        document.getElementById("folder-modal").classList.add("open");
    }
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
            const wasFromExplorer = editOpenedFromExplorer;
            editOpenedFromExplorer = false;
            closeEditLessonModal();
            await loadNotes();
            await loadPendingLessons();
            if (wasFromExplorer && currentFolderData && currentFolderData.current_full_path) {
                document.getElementById("folder-modal").classList.add("open");
                await fetchFolderContent(currentFolderData.current_full_path);
            }
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
