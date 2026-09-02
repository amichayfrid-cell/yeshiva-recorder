// State
let pendingLessons = [];
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
            window.location.href = "/login";
            return;
        }
        const data = await res.json();
        pendingLessons = data.lessons || [];

        document.getElementById("pending-count").innerText = pendingLessons.length;
        renderPendingLessons();
    } catch (e) {
        listContainer.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><h3>שגיאה בטעינת השיעורים</h3><p>${e.message}</p></div>`;
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
                <p>כל השיעורים מוינו בהצלחה! שיעורים חדשים יופיעו כאן מיד עם חיבור מקלט שמע.</p>
            </div>
        `;
        return;
    }

    listContainer.innerHTML = pendingLessons.map((lesson, index) => {
        const notesHtml = (lesson.notes && lesson.notes.length > 0) ? lesson.notes.map(note => `
            <div class="student-note-banner">
                <span class="icon">🔔</span>
                <div>
                    <div class="note-content"><strong>הערת תלמיד:</strong> ${escapeHtml(note.description)}</div>
                    <div class="note-meta">נשלח ע"י ${escapeHtml(note.student_name)} | ${note.created_at}</div>
                </div>
            </div>
        `).join("") : "";

        return `
            <div class="lesson-card" id="card-${index}">
                <div class="card-header">
                    <div class="card-title-wrap">
                        <span class="badge badge-hebrew-date">${escapeHtml(lesson.hebrew_date)}</span>
                        <span class="badge badge-time">שעת הקלטה: ${lesson.created_time}</span>
                        <span class="badge badge-time">${lesson.size_mb} MB</span>
                        <span class="card-title">${escapeHtml(lesson.filename)}</span>
                    </div>
                </div>

                ${notesHtml}

                <!-- Audio Player -->
                <div class="player-container">
                    <div class="audio-controls">
                        <button class="btn-icon" onclick="skipAudio('${index}', -10)" title="10 שניות אחורה">⏪ 10</button>
                        <button class="btn-icon btn-play" id="play-btn-${index}" onclick="togglePlay('${index}')">▶</button>
                        <button class="btn-icon" onclick="skipAudio('${index}', 10)" title="10 שניות קדימה">10 ⏩</button>
                    </div>
                    <div class="progress-wrap">
                        <input type="range" class="seek-bar" id="seek-${index}" value="0" min="0" step="0.1" onchange="seekAudio('${index}')">
                        <span class="time-display" id="time-${index}">00:00 / --:--</span>
                    </div>
                    <audio id="audio-${index}" src="/api/audio/stream?filename=${encodeURIComponent(lesson.filename).replace(/'/g, '%27')}" preload="metadata" ontimeupdate="updateProgress('${index}')" onloadedmetadata="initAudioDuration('${index}')" onended="onAudioEnded('${index}')"></audio>
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
                    <button class="btn btn-success" onclick="classifyLesson('${index}', '${encodeURIComponent(lesson.filename).replace(/'/g, '%27')}')">
                        💾 שמור וסווג
                    </button>
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
        audio.play();
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

    if (audio && audio.duration) {
        seek.value = (audio.currentTime / audio.duration) * 100;
        timeDisplay.innerText = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
    }
}

function initAudioDuration(index) {
    const audio = document.getElementById(`audio-${index}`);
    const timeDisplay = document.getElementById(`time-${index}`);
    if (audio && audio.duration) {
        timeDisplay.innerText = `00:00 / ${formatTime(audio.duration)}`;
    }
}

function seekAudio(index) {
    const audio = document.getElementById(`audio-${index}`);
    const seek = document.getElementById(`seek-${index}`);
    if (audio && audio.duration) {
        audio.currentTime = (seek.value / 100) * audio.duration;
    }
}

function onAudioEnded(index) {
    const btn = document.getElementById(`play-btn-${index}`);
    if (btn) btn.innerText = "▶";
}

function formatTime(seconds) {
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min < 10 ? '0' : ''}${min}:${sec < 10 ? '0' : ''}${sec}`;
}

// --- Instant Folder Explorer with Keyboard Navigation ---
async function fetchFolderContent(path = "") {
    const listContainer = document.getElementById("modal-folders-list");
    listContainer.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">טוען תיקייה...</div>`;

    try {
        const res = await fetch("/api/folders/list", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: path || null })
        });
        const data = await res.json();
        currentFolderData = data;
        highlightedFolderIndex = 0;
        renderExplorerView();
    } catch (e) {
        listContainer.innerHTML = `<div style="color:var(--danger); padding:1rem;">שגיאה: ${e.message}</div>`;
    }
}

function openFolderExplorer(cardIndex) {
    activeCardIndex = cardIndex;
    fetchFolderContent("");
    document.getElementById("folder-modal").classList.add("open");
}

function closeFolderModal() {
    document.getElementById("folder-modal").classList.remove("open");
    activeCardIndex = null;
}

function renderExplorerView() {
    if (!currentFolderData) return;

    const breadcrumbsContainer = document.getElementById("modal-breadcrumbs");
    const listContainer = document.getElementById("modal-folders-list");

    // 1. Breadcrumbs
    let parts = currentFolderData.current_rel_path ? currentFolderData.current_rel_path.split(/[\\/]/) : [];
    let breadcrumbsHtml = `
        <span class="crumb ${parts.length === 0 ? 'active' : ''}" onclick="fetchFolderContent('')">
            🏢 שרת הישיבה (ראשי)
        </span>
    `;

    let accumulatedPath = "";
    parts.forEach((part, idx) => {
        if (!part) return;
        accumulatedPath += (accumulatedPath ? "/" : "") + part;
        const isLast = idx === parts.length - 1;
        breadcrumbsHtml += `
            <span class="crumb-separator">❯</span>
            <span class="crumb ${isLast ? 'active' : ''}" onclick="${isLast ? '' : `fetchFolderByRelativePath('${escapeHtml(accumulatedPath)}')`}">
                ${escapeHtml(part)}
            </span>
        `;
    });
    breadcrumbsContainer.innerHTML = breadcrumbsHtml;

    // 2. Folder List (Without ".." row)
    const subfolders = currentFolderData.subfolders || [];

    if (subfolders.length === 0) {
        listContainer.innerHTML = `
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

    listContainer.innerHTML = subfolders.map((sub, idx) => `
        <div class="folder-row ${idx === highlightedFolderIndex ? 'highlighted' : ''}" 
             id="folder-item-${idx}" 
             onclick="handleItemClick(${idx})"
             onmouseenter="setHighlightedIndex(${idx})">
            <div style="display: flex; align-items: center; gap: 0.6rem;">
                <span>📁</span>
                <span style="font-weight: 500;">${escapeHtml(sub.name)}</span>
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

        // If typing in new folder input, allow normal typing
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
    if (activeCardIndex !== null && currentFolderData) {
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
async function classifyLesson(index, encodedFilename) {
    const filename = decodeURIComponent(encodedFilename);
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

    try {
        const form = new FormData();
        form.append("filename", filename);
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

function renderAllNotes() {
    const list = document.getElementById("notes-list");
    if (allNotes.length === 0) {
        list.innerHTML = `<div class="empty-state"><div class="icon">📬</div><h3>אין הערות חדשות מתלמידים</h3></div>`;
        return;
    }

    list.innerHTML = allNotes.map(note => `
        <div class="lesson-card">
            <div class="card-header">
                <div>
                    <span class="badge ${note.status === 'open' ? 'badge-alert' : 'badge-hebrew-date'}">${note.status === 'open' ? 'פתוחה' : 'טופלה'}</span>
                    <strong style="margin-right: 0.5rem;">${escapeHtml(note.filename)}</strong>
                </div>
                <span style="font-size: 0.8rem; color: var(--text-muted);">${note.created_at}</span>
            </div>
            <div style="margin: 0.75rem 0;">
                <p><strong>פירוט:</strong> ${escapeHtml(note.description)}</p>
                <p style="font-size: 0.85rem; color: var(--text-muted);"><strong>נשלח ע"י:</strong> ${escapeHtml(note.student_name)}</p>
            </div>
            ${note.status === 'open' ? `
                <button class="btn btn-outline" onclick="resolveNote(${note.id})">✓ סמן כטופל</button>
            ` : ''}
        </div>
    `).join("");
}

async function resolveNote(noteId) {
    const form = new FormData();
    form.append("note_id", noteId);
    form.append("status", "resolved");
    await fetch("/api/notes/status", { method: "POST", body: form });
    loadNotes();
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
