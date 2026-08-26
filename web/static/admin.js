// ==========================================================================
// Yeshiva Audio Management - Admin Dashboard Logic (Vanilla JS)
// ==========================================================================

let authToken = localStorage.getItem('yeshiva_admin_token') || '';
let knownRabbis = [];
let queueData = [];
let notesData = [];
let activeTab = 'queue';
let currentNoteFilter = 'open';

// Toast Notifications Helper
function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// Authenticated API Fetch Wrapper
async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  options.headers = headers;

  const response = await fetch(endpoint, options);
  if (response.status === 401) {
    // Token invalid or expired
    localStorage.removeItem('yeshiva_admin_token');
    authToken = '';
    showLoginModal();
    throw new Error('נדרשת התחברות מחדש');
  }
  return response;
}

// UI State & Modal Management
function showLoginModal() {
  document.getElementById('loginModal').style.display = 'flex';
  document.getElementById('dashboardView').style.display = 'none';
  document.getElementById('passwordInput').focus();
}

function showDashboard() {
  document.getElementById('loginModal').style.display = 'none';
  document.getElementById('dashboardView').style.display = 'block';
  refreshAllData();
}

function switchTab(tab) {
  activeTab = tab;
  document.getElementById('tabQueueBtn').classList.toggle('active', tab === 'queue');
  document.getElementById('tabNotesBtn').classList.toggle('active', tab === 'notes');
  document.getElementById('queueTabContent').style.display = tab === 'queue' ? 'block' : 'none';
  document.getElementById('notesTabContent').style.display = tab === 'notes' ? 'block' : 'none';
}

function filterNotes(filter) {
  currentNoteFilter = filter;
  document.getElementById('filterOpenNotesBtn').className = filter === 'open' ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';
  document.getElementById('filterAllNotesBtn').className = filter === 'all' ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';
  renderNotes();
}

// ==========================================
// Data Fetching & Population
// ==========================================
async function refreshAllData() {
  await Promise.all([
    fetchRabbis(),
    fetchQueue(),
    fetchNotes()
  ]);
}

async function fetchRabbis() {
  try {
    const res = await apiFetch('/api/rabbis');
    if (res.ok) {
      const data = await res.json();
      knownRabbis = data.rabbis || [];
    }
  } catch (e) {
    console.error('Error fetching rabbis:', e);
  }
}

async function fetchQueue() {
  try {
    const res = await apiFetch('/api/files/queue');
    if (res.ok) {
      const data = await res.json();
      queueData = data.files || [];
      document.getElementById('queueCountBadge').textContent = queueData.length;
      renderQueue();
    }
  } catch (e) {
    console.error('Error fetching queue:', e);
  }
}

async function fetchNotes() {
  try {
    const res = await apiFetch('/api/notes');
    if (res.ok) {
      const data = await res.json();
      notesData = data.notes || [];
      const openCount = notesData.filter(n => n.status === 'open').length;
      document.getElementById('notesCountBadge').textContent = openCount;
      renderNotes();
    }
  } catch (e) {
    console.error('Error fetching notes:', e);
  }
}

// ==========================================
// Queue Rendering (TAB 1)
// ==========================================
function renderQueue() {
  const container = document.getElementById('queueList');
  container.innerHTML = '';

  if (queueData.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🎉</div>
        <h3 style="font-size: 18px; margin-bottom: 6px;">אין שיעורים הממתינים למיון כרגע</h3>
        <p style="font-size: 14px;">כל ההקלטות שנקלטו מוינו ותויגו בהצלחה!</p>
      </div>
    `;
    return;
  }

  queueData.forEach((file, index) => {
    const card = document.createElement('div');
    card.className = `queue-card ${file.has_notes ? 'has-alert' : ''}`;
    card.id = `queue-card-${index}`;

    // Notes attached alert box
    let notesHtml = '';
    if (file.has_notes && file.notes && file.notes.length > 0) {
      const openNotes = file.notes.filter(n => n.status === 'open');
      if (openNotes.length > 0) {
        notesHtml = `
          <div class="attached-note-box">
            <span class="note-icon">📌</span>
            <div style="flex: 1;">
              <div style="font-size: 13px; font-weight: 700; color: var(--warning); margin-bottom: 2px;">
                הערת תלמיד על קובץ זה:
              </div>
              <div style="font-size: 14px; color: #78350f;">
                "${escapeHtml(openNotes[0].content)}"
              </div>
            </div>
          </div>
        `;
      }
    }

    // Rabbi Select Options
    let rabbiOptions = `<option value="">-- בחר רב מהרשימה --</option>`;
    knownRabbis.forEach(rabbi => {
      rabbiOptions += `<option value="${escapeHtml(rabbi)}">${escapeHtml(rabbi)}</option>`;
    });
    rabbiOptions += `<option value="__custom__">➕ הקלד שם רב חדש...</option>`;

    // Format audio stream URL
    const streamUrl = `/api/audio/stream?file=${encodeURIComponent(file.filename)}`;

    card.innerHTML = `
      <div class="file-meta-header">
        <div class="file-title-group">
          <span style="font-size: 20px;">🎵</span>
          <div>
            <div style="font-size: 16px; font-weight: 700; color: var(--text-primary); word-break: break-all;">
              ${escapeHtml(file.filename)}
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
              גודל: ${file.size_mb} MB • עודכן: ${formatDate(file.modified_at)}
            </div>
          </div>
        </div>
        <div>
          <span class="badge badge-neutral">${escapeHtml(file.location_label)}</span>
          ${file.has_notes ? '<span class="badge badge-warning">יש הערת תלמיד</span>' : ''}
        </div>
      </div>

      ${notesHtml}

      <div class="audio-player-container">
        <span style="font-size: 13px; font-weight: 700; color: var(--text-secondary); white-space: nowrap;">האזנה לפתיח:</span>
        <audio controls preload="none" src="${streamUrl}"></audio>
      </div>

      <form onsubmit="handleSortSubmit(event, ${index})" class="classification-grid">
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">שם הרב:</label>
          <div class="rabbi-select-wrapper">
            <select class="form-control" id="rabbi-select-${index}" onchange="handleRabbiSelectChange(${index})" required>
              ${rabbiOptions}
            </select>
            <input type="text" class="form-control" id="rabbi-custom-${index}" placeholder="הקלד שם רב חדש..." style="display: none; margin-top: 6px;">
          </div>
        </div>

        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">נושא השיעור:</label>
          <input type="text" class="form-control" id="topic-input-${index}" placeholder="לדוגמה: איסור והיתר, פרשת השבוע..." required>
        </div>

        <div class="form-group" style="margin-bottom: 0; min-width: 140px;">
          <label class="form-label">תאריך עברי (אופציונלי):</label>
          <input type="text" class="form-control" id="date-input-${index}" placeholder="למשל: ח_אלול_תשפו">
        </div>

        <div>
          <button type="submit" class="btn btn-success" id="sort-btn-${index}" style="height: 42px;">
            <span>💾 שמור וסווג</span>
          </button>
        </div>
      </form>
    `;

    container.appendChild(card);
  });
}

function handleRabbiSelectChange(index) {
  const select = document.getElementById(`rabbi-select-${index}`);
  const customInput = document.getElementById(`rabbi-custom-${index}`);
  if (select.value === '__custom__') {
    customInput.style.display = 'block';
    customInput.required = true;
    customInput.focus();
  } else {
    customInput.style.display = 'none';
    customInput.required = false;
  }
}

async function handleSortSubmit(e, index) {
  e.preventDefault();
  const file = queueData[index];
  if (!file) return;

  const select = document.getElementById(`rabbi-select-${index}`);
  const customInput = document.getElementById(`rabbi-custom-${index}`);
  const topicInput = document.getElementById(`topic-input-${index}`);
  const dateInput = document.getElementById(`date-input-${index}`);
  const btn = document.getElementById(`sort-btn-${index}`);

  const rabbi = select.value === '__custom__' ? customInput.value.trim() : select.value.trim();
  const topic = topicInput.value.trim();
  const hebrewDate = dateInput.value.trim() || null;

  if (!rabbi || !topic) {
    showToast('נא להזין שם רב ונושא', 'error');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'שומר...';

  // Find associated open note ID if any
  let noteIdToResolve = null;
  if (file.notes && file.notes.length > 0) {
    const openNote = file.notes.find(n => n.status === 'open');
    if (openNote) {
      noteIdToResolve = openNote.id;
    }
  }

  try {
    const res = await apiFetch('/api/files/sort', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: file.filename,
        current_location: file.filepath,
        rabbi_name: rabbi,
        topic: topic,
        hebrew_date: hebrewDate,
        note_id_to_resolve: noteIdToResolve
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'שגיאה בסיווג הקובץ');
    }

    const data = await res.json();
    showToast(`✓ הקובץ סווג בהצלחה: ${data.new_filename}`, 'success');

    // Refresh data
    refreshAllData();
  } catch (err) {
    showToast(err.message, 'error');
    btn.disabled = false;
    btn.textContent = '💾 שמור וסווג';
  }
}

// ==========================================
// Notes & Alerts Rendering (TAB 2)
// ==========================================
function renderNotes() {
  const container = document.getElementById('notesList');
  container.innerHTML = '';

  const filteredNotes = notesData.filter(n => {
    if (currentNoteFilter === 'open') return n.status === 'open';
    return true;
  });

  if (filteredNotes.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📬</div>
        <h3 style="font-size: 18px; margin-bottom: 6px;">אין הערות בתיבה</h3>
        <p style="font-size: 14px;">כל פניות התלמידים טופלו במלואן!</p>
      </div>
    `;
    return;
  }

  filteredNotes.forEach(note => {
    const card = document.createElement('div');
    card.className = `queue-card ${note.status === 'open' ? 'has-alert' : ''}`;

    const isResolved = note.status === 'resolved';
    const streamUrl = `/api/audio/stream?file=${encodeURIComponent(note.filename)}`;

    card.innerHTML = `
      <div class="file-meta-header">
        <div class="file-title-group">
          <span style="font-size: 22px;">📝</span>
          <div>
            <div style="font-size: 15px; font-weight: 700; color: var(--text-primary);">
              קובץ יעד: ${escapeHtml(note.filename)}
            </div>
            <div style="font-size: 12px; color: var(--text-muted);">
              נשלח ב: ${formatDate(note.created_at)}
            </div>
          </div>
        </div>
        <div>
          ${isResolved ? '<span class="badge badge-success">✓ טופל</span>' : '<span class="badge badge-warning">ממתין לטיפול</span>'}
        </div>
      </div>

      <div style="background: #f8fafc; border-right: 4px solid var(--primary); padding: 14px 18px; border-radius: var(--border-radius-md); margin-bottom: 16px;">
        <div style="font-size: 12px; font-weight: 700; color: var(--text-muted); margin-bottom: 4px;">תוכן ההערה:</div>
        <div style="font-size: 15px; color: var(--text-primary); line-height: 1.6; white-space: pre-wrap;">${escapeHtml(note.content)}</div>
      </div>

      <div class="audio-player-container">
        <span style="font-size: 13px; font-weight: 700; color: var(--text-secondary); white-space: nowrap;">האזנה לשיעור:</span>
        <audio controls preload="none" src="${streamUrl}"></audio>
      </div>

      <div style="display: flex; gap: 10px; justify-content: flex-end;">
        ${!isResolved ? `
          <button class="btn btn-success btn-sm" onclick="handleResolveNote('${note.id}')">
            ✓ סמן כטופל
          </button>
        ` : ''}
        <button class="btn btn-danger btn-sm" onclick="handleDeleteNote('${note.id}')">
          🗑 מחק
        </button>
      </div>
    `;

    container.appendChild(card);
  });
}

async function handleResolveNote(noteId) {
  try {
    const res = await apiFetch(`/api/notes/${noteId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resolution_note: 'סומן כטופל ידנית' })
    });
    if (res.ok) {
      showToast('ההערה סומנה כטופלה', 'success');
      fetchNotes();
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function handleDeleteNote(noteId) {
  if (!confirm('האם למחוק הערה זו לצמיתות?')) return;
  try {
    const res = await apiFetch(`/api/notes/${noteId}`, {
      method: 'DELETE'
    });
    if (res.ok) {
      showToast('ההערה נמחקה', 'success');
      fetchNotes();
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ==========================================
// Utilities & Initialization
// ==========================================
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, function(m) {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    }[m];
  });
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' });
  } catch (e) {
    return isoStr;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Login form handler
  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const pass = document.getElementById('passwordInput').value;
    const btn = document.getElementById('loginBtn');
    btn.disabled = true;

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pass })
      });

      if (!res.ok) {
        throw new Error('סיסמה שגויה');
      }

      const data = await res.json();
      authToken = data.token;
      localStorage.setItem('yeshiva_admin_token', authToken);
      document.getElementById('passwordInput').value = '';
      btn.disabled = false;
      showDashboard();
    } catch (err) {
      showToast(err.message || 'סיסמה שגויה', 'error');
      btn.disabled = false;
    }
  });

  // Logout button handler
  document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem('yeshiva_admin_token');
    authToken = '';
    showLoginModal();
  });

  // Refresh button handler
  document.getElementById('refreshBtn').addEventListener('click', () => {
    refreshAllData();
    showToast('הנתונים רועננו בהצלחה', 'success');
  });

  // Initial Auth Check
  if (authToken) {
    apiFetch('/api/auth/check')
      .then(res => {
        if (res.ok) {
          showDashboard();
        } else {
          showLoginModal();
        }
      })
      .catch(() => showLoginModal());
  } else {
    showLoginModal();
  }
});
