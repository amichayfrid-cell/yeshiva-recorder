// ==========================================================================
// Rav Tzvi Protected Library - Explorer & Audio Player Logic (Vanilla JS)
// ==========================================================================

let currentSubpath = '';
let historyStack = [];
let loadedFolders = [];
let loadedFiles = [];
let currentPlayingSubpath = '';

const audio = document.getElementById('audioPlayer');
const playIcon = document.getElementById('playIcon');
const playerTrackName = document.getElementById('playerTrackName');
const progressSlider = document.getElementById('progressSlider');
const currentTimeLabel = document.getElementById('currentTimeLabel');
const totalDurationLabel = document.getElementById('totalDurationLabel');
const speedSelect = document.getElementById('speedSelect');
const volumeSlider = document.getElementById('volumeSlider');
const volumeIcon = document.getElementById('volumeIcon');
const backBtn = document.getElementById('backBtn');
const breadcrumbsContainer = document.getElementById('breadcrumbsContainer');
const searchInput = document.getElementById('searchInput');

let searchDebounceTimer = null;
let isSearching = false;
let currentBreadcrumbs = [];

// ==========================================
// Folder Navigation & API Fetch
// ==========================================
async function loadFolder(subpath = '', pushHistory = true) {
  try {
    if (pushHistory && currentSubpath !== subpath) {
      historyStack.push(currentSubpath);
    }
    currentSubpath = subpath;
    isSearching = false;
    backBtn.disabled = historyStack.length === 0;
    searchInput.value = '';

    const res = await fetch(`/api/rav-tzvi/browse?subpath=${encodeURIComponent(subpath)}`);
    if (!res.ok) {
      throw new Error('שגיאה בטעינת התיקייה');
    }

    const data = await res.json();
    loadedFolders = data.folders || [];
    loadedFiles = data.files || [];
    currentBreadcrumbs = data.breadcrumbs || [];

    renderBreadcrumbs(currentBreadcrumbs);
    renderExplorer(loadedFolders, loadedFiles);
  } catch (err) {
    console.error('Error loading folder:', err);
  }
}

function navigateBack() {
  if (isSearching) {
    clearSearch();
    return;
  }
  if (historyStack.length > 0) {
    const prev = historyStack.pop();
    loadFolder(prev, false);
  }
}

function clearSearch() {
  searchInput.value = '';
  isSearching = false;
  renderBreadcrumbs(currentBreadcrumbs);
  renderExplorer(loadedFolders, loadedFiles);
}

function renderBreadcrumbs(crumbs) {
  breadcrumbsContainer.innerHTML = '';
  crumbs.forEach((crumb, idx) => {
    const isLast = idx === crumbs.length - 1;
    if (isLast) {
      const span = document.createElement('span');
      span.className = 'crumb-current';
      span.textContent = crumb.name;
      breadcrumbsContainer.appendChild(span);
    } else {
      const a = document.createElement('span');
      a.className = 'crumb-link';
      a.textContent = crumb.name;
      a.onclick = () => loadFolder(crumb.subpath);
      breadcrumbsContainer.appendChild(a);

      const sep = document.createElement('span');
      sep.className = 'crumb-separator';
      sep.textContent = '>';
      breadcrumbsContainer.appendChild(sep);
    }
  });
}

function renderExplorer(folders, files, isSearchResult = false) {
  const foldersGrid = document.getElementById('foldersGrid');
  const filesList = document.getElementById('filesList');
  const foldersSection = document.getElementById('foldersSection');
  const filesSection = document.getElementById('filesSection');
  const emptyView = document.getElementById('emptyView');

  foldersGrid.innerHTML = '';
  filesList.innerHTML = '';

  // Render Folders
  if (folders.length > 0) {
    foldersSection.style.display = 'block';
    folders.forEach(folder => {
      const card = document.createElement('div');
      card.className = 'folder-card';
      card.onclick = () => loadFolder(folder.subpath);

      let subText = '';
      if (isSearchResult && folder.folder_path) {
        subText = `נתיב: ${folder.folder_path}`;
      } else {
        if (folder.audio_count > 0) subText += `${folder.audio_count} שיעורים`;
        if (folder.subfolder_count > 0) {
          if (subText) subText += ' • ';
          subText += `${folder.subfolder_count} תת-תיקיות`;
        }
        if (!subText) subText = 'תיקייה';
      }

      card.innerHTML = `
        <span class="folder-icon">📁</span>
        <div style="flex: 1; min-width: 0;">
          <div class="folder-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div>
          <div class="folder-sub">${escapeHtml(subText)}</div>
        </div>
      `;
      foldersGrid.appendChild(card);
    });
  } else {
    foldersSection.style.display = 'none';
  }

  // Render Files
  if (files.length > 0) {
    filesSection.style.display = 'block';
    files.forEach(file => {
      const row = document.createElement('div');
      const isPlaying = currentPlayingSubpath === file.subpath;
      row.className = `file-row ${isPlaying ? 'playing' : ''}`;
      row.id = `file-row-${encodeId(file.subpath)}`;
      row.onclick = () => playAudio(file.subpath, file.filename);

      let metaText = `גודל: ${file.size_mb} MB`;
      if (isSearchResult && file.folder_path) {
        metaText = `מיקום: ${file.folder_path} • ${metaText}`;
      }

      row.innerHTML = `
        <span class="file-icon">${isPlaying ? '🔊' : '🎵'}</span>
        <div class="file-info">
          <div class="file-title" title="${escapeHtml(file.filename)}">${escapeHtml(file.filename)}</div>
          <div class="file-meta">${escapeHtml(metaText)}</div>
        </div>
        <button class="file-action-btn" onclick="event.stopPropagation(); playAudio('${escapeJsStr(file.subpath)}', '${escapeJsStr(file.filename)}')">
          <span>${isPlaying && !audio.paused ? 'השהה ⏸' : 'השמע ▶'}</span>
        </button>
      `;
      filesList.appendChild(row);
    });
  } else {
    filesSection.style.display = 'none';
  }

  // Handle empty folder
  if (folders.length === 0 && files.length === 0) {
    emptyView.style.display = 'block';
  } else {
    emptyView.style.display = 'none';
  }
}

function handleSearch() {
  const query = searchInput.value.trim();
  clearTimeout(searchDebounceTimer);

  if (!query) {
    clearSearch();
    return;
  }

  searchDebounceTimer = setTimeout(async () => {
    isSearching = true;
    try {
      const res = await fetch(`/api/rav-tzvi/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) return;
      const data = await res.json();

      // Show search breadcrumb
      breadcrumbsContainer.innerHTML = `
        <span class="crumb-link" onclick="clearSearch()">🏠 שיעורי הרב צבי</span>
        <span class="crumb-separator">&gt;</span>
        <span class="crumb-current">תוצאות חיפוש בכל הספרייה: "${escapeHtml(query)}" (${data.total_items})</span>
      `;

      renderExplorer(data.folders || [], data.files || [], true);
    } catch (e) {
      console.error('Search error:', e);
    }
  }, 200);
}

// ==========================================
// Audio Player Controls & Logic
// ==========================================
function playAudio(fileSubpath, filename) {
  if (currentPlayingSubpath === fileSubpath) {
    togglePlayPause();
    return;
  }

  currentPlayingSubpath = fileSubpath;
  playerTrackName.textContent = filename.replace(/\.[^/.]+$/, ''); // Strip extension
  playerTrackName.title = filename;

  const streamUrl = `/api/rav-tzvi/stream?file=${encodeURIComponent(fileSubpath)}`;
  audio.src = streamUrl;
  audio.playbackRate = parseFloat(speedSelect.value) || 1.0;
  audio.play();

  highlightPlayingFile();
}

function togglePlayPause() {
  if (!audio.src) return;
  if (audio.paused) {
    audio.play();
  } else {
    audio.pause();
  }
}

function seekRelative(seconds) {
  if (!audio.src || isNaN(audio.duration)) return;
  audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + seconds));
}

function handleSeek(val) {
  if (!audio.src || isNaN(audio.duration)) return;
  const targetTime = (val / 100) * audio.duration;
  audio.currentTime = targetTime;
}

function changePlaybackSpeed(speed) {
  audio.playbackRate = parseFloat(speed) || 1.0;
}

function handleVolume(val) {
  audio.volume = parseFloat(val);
  audio.muted = false;
  updateVolumeIcon();
}

function toggleMute() {
  audio.muted = !audio.muted;
  updateVolumeIcon();
}

function updateVolumeIcon() {
  if (audio.muted || audio.volume === 0) {
    volumeIcon.textContent = '🔇';
  } else if (audio.volume < 0.5) {
    volumeIcon.textContent = '🔉';
  } else {
    volumeIcon.textContent = '🔊';
  }
}

function highlightPlayingFile() {
  document.querySelectorAll('.file-row').forEach(row => {
    row.classList.remove('playing');
    const btn = row.querySelector('.file-action-btn span');
    if (btn) btn.textContent = 'השמע ▶';
    const icon = row.querySelector('.file-icon');
    if (icon) icon.textContent = '🎵';
  });

  const activeRow = document.getElementById(`file-row-${encodeId(currentPlayingSubpath)}`);
  if (activeRow) {
    activeRow.classList.add('playing');
    const btn = activeRow.querySelector('.file-action-btn span');
    if (btn) btn.textContent = audio.paused ? 'השמע ▶' : 'השהה ⏸';
    const icon = activeRow.querySelector('.file-icon');
    if (icon) icon.textContent = '🔊';
  }
}

// Audio Event Handlers
audio.addEventListener('play', () => {
  playIcon.textContent = '⏸';
  highlightPlayingFile();
});

audio.addEventListener('pause', () => {
  playIcon.textContent = '▶';
  highlightPlayingFile();
});

audio.addEventListener('timeupdate', () => {
  if (!isNaN(audio.duration) && audio.duration > 0) {
    const percent = (audio.currentTime / audio.duration) * 100;
    progressSlider.value = percent;
    currentTimeLabel.textContent = formatTime(audio.currentTime);
  }
});

audio.addEventListener('loadedmetadata', () => {
  totalDurationLabel.textContent = formatTime(audio.duration);
  audio.playbackRate = parseFloat(speedSelect.value) || 1.0;
});

audio.addEventListener('ended', () => {
  playIcon.textContent = '▶';
  progressSlider.value = 0;
  highlightPlayingFile();
});

// Format seconds to mm:ss or hh:mm:ss
function formatTime(seconds) {
  if (isNaN(seconds) || seconds === Infinity) return '00:00';
  const s = Math.floor(seconds);
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Helpers
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m]));
}

function escapeJsStr(str) {
  if (!str) return '';
  return str.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function encodeId(str) {
  return btoa(unescape(encodeURIComponent(str))).replace(/[^a-zA-Z0-9]/g, '_');
}

// ==========================================
// Anti-Download Protections
// ==========================================
document.addEventListener('contextmenu', e => e.preventDefault());
document.addEventListener('keydown', e => {
  // Block Ctrl+S (Save), Ctrl+U (Source), Ctrl+Shift+I (DevTools)
  if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S' || e.key === 'u' || e.key === 'U')) {
    e.preventDefault();
  }
  // Keyboard navigation & seeking shortcuts
  if (e.target.tagName !== 'INPUT') {
    // Spacebar to play/pause
    if (e.code === 'Space') {
      e.preventDefault();
      togglePlayPause();
    }
    // Left/Right Arrow keys: +-10 seconds
    if (e.code === 'ArrowLeft') {
      e.preventDefault();
      seekRelative(10);  // Forward in RTL timeline
    }
    if (e.code === 'ArrowRight') {
      e.preventDefault();
      seekRelative(-10); // Rewind in RTL timeline
    }
    // Up/Down Arrow keys: +-60 seconds (1 minute)
    if (e.code === 'ArrowUp') {
      e.preventDefault();
      seekRelative(60);  // +1 minute
    }
    if (e.code === 'ArrowDown') {
      e.preventDefault();
      seekRelative(-60); // -1 minute
    }
  }
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  loadFolder('');
});
