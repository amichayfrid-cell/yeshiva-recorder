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
  currentNavIndex = -1;

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
async function playAudio(fileSubpath, filename) {
  if (currentPlayingSubpath === fileSubpath) {
    togglePlayPause();
    return;
  }

  currentPlayingSubpath = fileSubpath;
  playerTrackName.textContent = 'טוען... ' + filename.replace(/\.[^/.]+$/, '');
  playerTrackName.title = filename;
  playIcon.textContent = '⏳';

  try {
    const tokenRes = await fetch(`/api/rav-tzvi/token?file=${encodeURIComponent(fileSubpath)}`, { method: 'POST' });
    if (!tokenRes.ok) throw new Error('Token error');
    const tokenData = await tokenRes.json();
    
    const streamUrl = `/api/rav-tzvi/stream?file=${encodeURIComponent(fileSubpath)}&token=${tokenData.token}`;
    audio.src = streamUrl;
    audio.playbackRate = parseFloat(speedSelect.value) || 1.0;
    playerTrackName.textContent = filename.replace(/\.[^/.]+$/, '');
    audio.play();
    
    highlightPlayingFile();
  } catch (e) {
    console.error("Error playing audio:", e);
    playIcon.textContent = '▶';
    alert("שגיאה בטעינת השיעור או שפג תוקף הקישור.");
  }
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

audio.addEventListener('waiting', () => {
  playIcon.textContent = '⏳';
});

audio.addEventListener('playing', () => {
  playIcon.textContent = '⏸';
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
// Keyboard Navigation & Shortcuts
// ==========================================
let currentNavIndex = -1;

function getNavigableItems() {
  return Array.from(document.querySelectorAll('.folder-card, .file-row'));
}

function updateNavSelection(newIndex) {
  const items = getNavigableItems();
  if (items.length === 0) {
    currentNavIndex = -1;
    return;
  }
  if (newIndex < 0) newIndex = 0;
  if (newIndex >= items.length) newIndex = items.length - 1;
  currentNavIndex = newIndex;

  items.forEach((item, idx) => {
    if (idx === currentNavIndex) {
      item.classList.add('selected');
      item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    } else {
      item.classList.remove('selected');
    }
  });
}

function moveSpatial(direction) {
  const items = getNavigableItems();
  if (items.length === 0) return;

  if (currentNavIndex < 0 || currentNavIndex >= items.length) {
    updateNavSelection(0);
    return;
  }

  const currentEl = items[currentNavIndex];
  const cRect = currentEl.getBoundingClientRect();
  const cx = cRect.left + cRect.width / 2;
  const cy = cRect.top + cRect.height / 2;

  let bestIndex = -1;
  let bestScore = Infinity;

  items.forEach((item, idx) => {
    if (idx === currentNavIndex) return;
    const rect = item.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const dx = x - cx;
    const dy = y - cy;

    if (direction === 'down') {
      if (dy > 15) {
        const score = dy * 1.5 + Math.abs(dx);
        if (score < bestScore) {
          bestScore = score;
          bestIndex = idx;
        }
      }
    } else if (direction === 'up') {
      if (dy < -15) {
        const score = -dy * 1.5 + Math.abs(dx);
        if (score < bestScore) {
          bestScore = score;
          bestIndex = idx;
        }
      }
    } else if (direction === 'right') {
      if (dx > 15) {
        const score = Math.abs(dy) * 4 + dx;
        if (score < bestScore) {
          bestScore = score;
          bestIndex = idx;
        }
      }
    } else if (direction === 'left') {
      if (dx < -15) {
        const score = Math.abs(dy) * 4 - dx;
        if (score < bestScore) {
          bestScore = score;
          bestIndex = idx;
        }
      }
    }
  });

  if (bestIndex !== -1) {
    updateNavSelection(bestIndex);
  } else {
    // If no element in that direction (e.g., in files list or at borders), seek audio
    if (direction === 'right' && audio.src) {
      seekRelative(10);
    } else if (direction === 'left' && audio.src) {
      seekRelative(-10);
    }
  }
}

document.addEventListener('contextmenu', e => e.preventDefault());
document.addEventListener('keydown', e => {
  // Block browser save/source shortcuts
  if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S' || e.key === 'u' || e.key === 'U')) {
    e.preventDefault();
    return;
  }

  const isInputFocused = e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT';

  // Quick search shortcut: '/' or 'Ctrl+F'
  if (!isInputFocused && (e.key === '/' || (e.ctrlKey && (e.key === 'f' || e.key === 'F')))) {
    e.preventDefault();
    searchInput.focus();
    searchInput.select();
    return;
  }

  // Escape: exit search or navigate back
  if (e.key === 'Escape') {
    if (document.activeElement === searchInput) {
      searchInput.value = '';
      handleSearch();
      searchInput.blur();
    } else {
      navigateBack();
    }
    return;
  }

  // If focused on an input field, Enter focuses the first result
  if (isInputFocused) {
    if (e.key === 'Enter') {
      searchInput.blur();
      updateNavSelection(0);
    }
    return;
  }

  // Dedicated Audio Seek: Shift + Right/Left Arrow
  if (e.shiftKey && e.code === 'ArrowRight') {
    e.preventDefault();
    seekRelative(10);
    return;
  }
  if (e.shiftKey && e.code === 'ArrowLeft') {
    e.preventDefault();
    seekRelative(-10);
    return;
  }

  // 2D Spatial Grid Navigation: Up / Down / Right / Left
  if (e.code === 'ArrowDown') {
    e.preventDefault();
    moveSpatial('down');
    return;
  }
  if (e.code === 'ArrowUp') {
    e.preventDefault();
    moveSpatial('up');
    return;
  }
  if (e.code === 'ArrowRight') {
    e.preventDefault();
    moveSpatial('right');
    return;
  }
  if (e.code === 'ArrowLeft') {
    e.preventDefault();
    moveSpatial('left');
    return;
  }

  // Enter to open folder or play lesson
  if (e.key === 'Enter') {
    const items = getNavigableItems();
    if (currentNavIndex >= 0 && currentNavIndex < items.length) {
      e.preventDefault();
      items[currentNavIndex].click();
      return;
    }
  }

  // Backspace or Alt+Left to go back to parent folder
  if (e.key === 'Backspace' || (e.altKey && e.key === 'ArrowLeft')) {
    e.preventDefault();
    navigateBack();
    return;
  }

  // Spacebar to play/pause audio
  if (e.code === 'Space') {
    e.preventDefault();
    togglePlayPause();
    return;
  }

  // Mute toggle: 'm' or 'M' or 'צ' (Hebrew keyboard layout for M)
  if (e.key === 'm' || e.key === 'M' || e.key === 'צ') {
    e.preventDefault();
    toggleMute();
    return;
  }
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  loadFolder('');
});
