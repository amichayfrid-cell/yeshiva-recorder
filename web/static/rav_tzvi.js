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
const videoModal = document.getElementById('videoModal');
const videoPlayer = document.getElementById('videoPlayer');
const videoModalTitle = document.getElementById('videoModalTitle');
const docModal = document.getElementById('docModal');
const docModalTitle = document.getElementById('docModalTitle');
const docModalIcon = document.getElementById('docModalIcon');
const docContent = document.getElementById('docContent');
const protectionToast = document.getElementById('protectionToast');

function isVideoFile(fn) {
  if (!fn) return false;
  const lower = fn.toLowerCase().trim();
  return ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.3gp', '.mpg', '.mpeg', '.ts', '.asf', '.vob', '.ogv'].some(ext => lower.endsWith(ext));
}

function isDocFile(fn) {
  if (!fn) return false;
  const lower = fn.toLowerCase().trim();
  return ['.pdf', '.doc', '.docx', '.txt', '.ppt', '.pptx', '.odt', '.rtf', '.xls', '.xlsx'].some(ext => lower.endsWith(ext));
}

function isImageFile(fn) {
  if (!fn) return false;
  const lower = fn.toLowerCase().trim();
  return ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff', '.heic', '.svg'].some(ext => lower.endsWith(ext));
}

let searchDebounceTimer = null;
let isSearching = false;
let currentBreadcrumbs = [];
let currentNetworkStatus = null;
let activeBrowseController = null;
let activeSearchController = null;

function showLoadingState(message = 'טוען תוכן תיקייה...') {
  const foldersSection = document.getElementById('foldersSection');
  const filesSection = document.getElementById('filesSection');
  const emptyView = document.getElementById('emptyView');
  if (foldersSection) foldersSection.style.display = 'none';
  if (filesSection) filesSection.style.display = 'none';
  if (emptyView) {
    emptyView.style.display = 'block';
    const emptyIcon = document.getElementById('emptyIcon');
    const emptyTitle = document.getElementById('emptyTitle');
    const emptySubtext = document.getElementById('emptySubtext');
    if (emptyIcon) emptyIcon.innerHTML = '<div class="spinner"></div>';
    if (emptyTitle) emptyTitle.textContent = message;
    if (emptySubtext) emptySubtext.textContent = 'אנא המתן';
  }
}

function showErrorState(title = 'שגיאה בטעינה', message = '') {
  const foldersSection = document.getElementById('foldersSection');
  const filesSection = document.getElementById('filesSection');
  const emptyView = document.getElementById('emptyView');
  if (foldersSection) foldersSection.style.display = 'none';
  if (filesSection) filesSection.style.display = 'none';
  if (emptyView) {
    emptyView.style.display = 'block';
    const emptyIcon = document.getElementById('emptyIcon');
    const emptyTitle = document.getElementById('emptyTitle');
    const emptySubtext = document.getElementById('emptySubtext');
    if (emptyIcon) emptyIcon.textContent = '⚠️';
    if (emptyTitle) emptyTitle.textContent = title;
    if (emptySubtext) {
      emptySubtext.innerHTML = `
        <div>${escapeHtml(message)}</div>
        <button class="nav-btn" style="margin-top: 14px; cursor: pointer;" onclick="loadFolder(currentSubpath, false)">
          <span>🔄 נסה שוב</span>
        </button>
      `;
    }
  }
}

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

    if (activeBrowseController) {
      activeBrowseController.abort();
    }
    activeBrowseController = new AbortController();

    showLoadingState('טוען תיקייה...');

    // 25s timeout to avoid indefinite spinner hang
    const fetchTimeout = setTimeout(() => {
      if (activeBrowseController) {
        activeBrowseController.abort();
      }
    }, 25000);

    const res = await fetch(`/api/rav-tzvi/browse?subpath=${encodeURIComponent(subpath)}`, {
      signal: activeBrowseController.signal
    });
    clearTimeout(fetchTimeout);

    if (!res.ok) {
      throw new Error(`שגיאה בטעינת התיקייה (${res.status})`);
    }

    const data = await res.json();
    loadedFolders = data.folders || [];
    loadedFiles = data.files || [];
    currentBreadcrumbs = data.breadcrumbs || [];
    currentNetworkStatus = data.network_status || null;

    updateNetworkBanner(currentNetworkStatus);
    renderBreadcrumbs(currentBreadcrumbs);
    renderExplorer(loadedFolders, loadedFiles);
  } catch (err) {
    if (err.name === 'AbortError') {
      console.warn('Browse request aborted or timed out');
      showErrorState('הטעינה התעכבה או בוטלה', 'ייתכן ששרת הקבצים של הישיבה עמוס כרגע. אנא נסה שוב.');
    } else {
      console.error('Error loading folder:', err);
      showErrorState('שגיאה בטעינת התיקייה', err.message || 'לא ניתן לתקשר עם שרת הישיבה כעת');
    }
  }
}

function updateNetworkBanner(status) {
  const alertEl = document.getElementById('networkAlert');
  if (!alertEl) return;
  if (status && status.mounted === false) {
    alertEl.style.display = 'flex';
    const pathEl = document.getElementById('networkMountPath');
    if (pathEl && status.mount_point) {
      pathEl.textContent = status.mount_point;
    }
  } else {
    alertEl.style.display = 'none';
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
          <div class="folder-name" style="white-space: normal !important; word-break: break-word !important; overflow-wrap: break-word !important; line-height: 1.4 !important; display: block !important;" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div>
          <div class="folder-sub">${escapeHtml(subText)}</div>
        </div>
      `;
      foldersGrid.appendChild(card);
    });
  } else {
    foldersSection.style.display = 'none';
  }

  // Render Files (Audio and Video)
  if (files.length > 0) {
    filesSection.style.display = 'block';
    files.forEach(file => {
      const isImage = file.is_image || isImageFile(file.filename);
      const isDoc = !isImage && (file.is_doc || isDocFile(file.filename));
      const isOpenable = isDoc || isImage;
      const isVideo = !isOpenable && (file.is_video || isVideoFile(file.filename));
      const row = document.createElement('div');
      const isPlaying = currentPlayingSubpath === file.subpath;
      row.className = `file-row ${isPlaying ? 'playing' : ''} ${isVideo ? 'is-video' : ''} ${isOpenable ? 'is-doc' : ''}`;
      row.id = `file-row-${encodeId(file.subpath)}`;
      row.dataset.subpath = file.subpath;
      row.onclick = () => isOpenable 
        ? openDocument(file.subpath, file.filename) 
        : (isVideo ? playVideo(file.subpath, file.filename) : playAudio(file.subpath, file.filename));

      let metaText = `גודל: ${file.size_mb} MB`;
      if (isSearchResult && file.folder_path) {
        metaText = `מיקום: ${file.folder_path} • ${metaText}`;
      }

      const fileIcon = isImage ? '🖼️' : (isDoc ? '📄' : (isVideo ? '🎬' : (isPlaying ? '🔊' : '🎵')));
      const actionText = isImage
        ? 'הצג תמונה ↗'
        : (isDoc 
          ? 'צפה במסמך ↗' 
          : (isVideo 
            ? 'צפה בסרטון ▶' 
            : (isPlaying && !audio.paused ? 'השהה ⏸' : 'השמע ▶')));
      const tagHtml = isImage
        ? '<span class="video-tag" style="background:#059669; color:#fff;">תמונה</span>'
        : (isDoc 
          ? '<span class="video-tag" style="background:#2563eb; color:#fff;">מסמך</span>' 
          : (isVideo ? '<span class="video-tag">וידאו</span>' : ''));

      row.innerHTML = `
        <span class="file-icon">${fileIcon}</span>
        <div class="file-info">
          <div class="file-title" title="${escapeHtml(file.filename)}">
            ${tagHtml}${escapeHtml(file.filename)}
          </div>
          <div class="file-meta">${escapeHtml(metaText)}</div>
        </div>
        <button class="file-action-btn" onclick="event.stopPropagation(); this.closest('.file-row').click();">
          <span>${actionText}</span>
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
    const emptyIcon = document.getElementById('emptyIcon');
    const emptyTitle = document.getElementById('emptyTitle');
    const emptySubtext = document.getElementById('emptySubtext');

    if (currentNetworkStatus && currentNetworkStatus.mounted === false) {
      if (emptyIcon) emptyIcon.textContent = '🔌';
      if (emptyTitle) emptyTitle.textContent = 'שרת הקבצים של הישיבה אינו מעוגן';
      if (emptySubtext) emptySubtext.textContent = 'לא ניתן להציג את שיעורי הרב צבי כיוון ששיתוף הרשת אינו מחובר כרגע. יש לבצע עגינה (sudo mount -a) בשרת הישיבה.';
    } else {
      if (emptyIcon) emptyIcon.textContent = '📂';
      if (emptyTitle) emptyTitle.textContent = isSearchResult ? 'לא נמצאו שיעורים התואמים לחיפוש' : 'אין פריטים להצגה בתיקייה זו';
      if (emptySubtext) emptySubtext.textContent = '';
    }
  } else {
    emptyView.style.display = 'none';
  }
}

function handleSearch() {
  const query = searchInput.value.trim();
  clearTimeout(searchDebounceTimer);

  if (!query) {
    if (activeSearchController) {
      activeSearchController.abort();
    }
    clearSearch();
    return;
  }

  // Require at least 2 characters for library-wide search
  if (query.length < 2) {
    return;
  }

  searchDebounceTimer = setTimeout(async () => {
    isSearching = true;
    if (activeSearchController) {
      activeSearchController.abort();
    }
    activeSearchController = new AbortController();

    showLoadingState(`מחפש בספרייה "${escapeHtml(query)}"...`);
    const searchIcon = document.querySelector('.search-icon');
    if (searchIcon) searchIcon.textContent = '⏳';

    try {
      const res = await fetch(`/api/rav-tzvi/search?q=${encodeURIComponent(query)}`, {
        signal: activeSearchController.signal
      });
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
      if (e.name !== 'AbortError') {
        console.error('Search error:', e);
      }
    } finally {
      if (searchIcon) searchIcon.textContent = '🔍';
    }
  }, 400);
}

// ==========================================
// Document Viewer Logic (Protected In-Browser Preview)
// ==========================================
let currentDocScale = 17;
let toastTimeout = null;

function showProtectionToast(msg = '🔒 העתקה, שמירה והדפסה חסומות להגנה על זכויות יוצרים') {
  const toast = document.getElementById('protectionToast');
  if (!toast) return;
  toast.textContent = msg;
  toast.style.display = 'flex';
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toast.style.display = 'none';
  }, 2500);
}

async function openDocument(fileSubpath, filename) {
  // Pause any audio playing in background
  if (audio && !audio.paused) {
    audio.pause();
    playIcon.textContent = '▶';
  }

  const modal = document.getElementById('docModal');
  const title = document.getElementById('docModalTitle');
  const icon = document.getElementById('docModalIcon');
  const content = document.getElementById('docContent');

  if (!modal || !content) return;

  const isImage = isImageFile(filename);
  if (title) title.textContent = filename || 'צפייה במסמך';
  if (icon) icon.textContent = isImage ? '🖼️' : '📄';

  currentDocScale = 17;
  content.style.fontSize = `${currentDocScale}px`;
  content.innerHTML = `
    <div class="doc-loading">
      <span class="doc-spinner">⏳</span>
      <span>טוען מסמך באוויר... אנא המתן</span>
    </div>
  `;

  modal.style.display = 'flex';

  try {
    const tokenRes = await fetch(`/api/rav-tzvi/token?file=${encodeURIComponent(fileSubpath)}`, { method: 'POST' });
    if (!tokenRes.ok) throw new Error('Token error');
    const tokenData = await tokenRes.json();

    const viewRes = await fetch(`/api/rav-tzvi/view-doc?file=${encodeURIComponent(fileSubpath)}&token=${tokenData.token}`);
    if (!viewRes.ok) {
      const errJson = await viewRes.json().catch(() => ({ detail: 'שגיאה בטעינת המסמך' }));
      throw new Error(errJson.detail || 'שגיאה בטעינת המסמך');
    }

    const data = await viewRes.json();

    if (data.type === 'html') {
      content.innerHTML = data.html;
    } else if (data.type === 'image') {
      content.innerHTML = `
        <div class="doc-image-wrapper">
          <img src="${data.stream_url}" class="doc-preview-img" draggable="false" oncontextmenu="return false;" alt="${escapeHtml(filename)}">
        </div>
      `;
    } else if (data.type === 'pdf') {
      content.innerHTML = `
        <iframe src="${data.stream_url}#toolbar=0&navpanes=0" class="doc-preview-pdf" frameborder="0"></iframe>
      `;
    } else {
      content.innerHTML = `<div class="doc-notice">${escapeHtml(data.message || 'אין תצוגה זמינה')}</div>`;
    }
  } catch (err) {
    console.error("Error viewing document:", err);
    content.innerHTML = `
      <div style="text-align: center; padding: 40px 20px; color: #ef4444;">
        <div style="font-size: 36px; margin-bottom: 8px;">⚠️</div>
        <div style="font-weight: 700; font-size: 16px;">שגיאה בפתיחת המסמך באוויר</div>
        <div style="font-size: 13px; color: #64748b; margin-top: 4px;">${escapeHtml(err.message || 'לא ניתן לטעון את הקובץ')}</div>
      </div>
    `;
  }
}

function closeDocViewer() {
  const modal = document.getElementById('docModal');
  const content = document.getElementById('docContent');
  if (modal) modal.style.display = 'none';
  if (content) content.innerHTML = '';
}

function zoomDoc(delta) {
  const content = document.getElementById('docContent');
  if (!content) return;
  currentDocScale = Math.max(12, Math.min(28, currentDocScale + delta * 2));
  content.style.fontSize = `${currentDocScale}px`;
}

function resetDocZoom() {
  const content = document.getElementById('docContent');
  if (!content) return;
  currentDocScale = 17;
  content.style.fontSize = `${currentDocScale}px`;
}

function toggleDocFullscreen() {
  const modal = document.getElementById('docModal');
  if (!modal) return;
  const container = modal.querySelector('.doc-modal-container');
  if (!container) return;
  if (!document.fullscreenElement) {
    container.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
}

// ==========================================
// Video Player Modal Logic
// ==========================================
async function playVideo(fileSubpath, filename) {
  // Pause any audio playing in background
  if (audio && !audio.paused) {
    audio.pause();
    playIcon.textContent = '▶';
  }

  currentPlayingSubpath = fileSubpath;
  highlightPlayingFile();

  if (videoModalTitle) {
    videoModalTitle.textContent = filename.replace(/\.[^/.]+$/, '');
  }
  if (videoModal) {
    videoModal.style.display = 'flex';
  }
  if (videoPlayer) {
    videoPlayer.pause();
    videoPlayer.src = '';
  }

  try {
    const tokenRes = await fetch(`/api/rav-tzvi/token?file=${encodeURIComponent(fileSubpath)}`, { method: 'POST' });
    if (!tokenRes.ok) throw new Error('Token error');
    const tokenData = await tokenRes.json();

    const streamUrl = `/api/rav-tzvi/stream?file=${encodeURIComponent(fileSubpath)}&token=${tokenData.token}`;
    if (videoPlayer) {
      videoPlayer.src = streamUrl;
      videoPlayer.playbackRate = parseFloat(speedSelect.value) || 1.0;
      try {
        await videoPlayer.play();
      } catch (playErr) {
        if (playErr.name !== 'AbortError') {
          console.warn("Video play warning:", playErr);
        }
      }
    }
  } catch (err) {
    console.error("Error playing video:", err);
    alert("שגיאה בטעינת קובץ הווידאו או שפג תוקף הקישור.");
  }
}

function closeVideoPlayer() {
  if (videoPlayer) {
    videoPlayer.pause();
    videoPlayer.src = '';
  }
  if (videoModal) {
    videoModal.style.display = 'none';
  }
}

function toggleVideoFullscreen() {
  if (!videoPlayer) return;
  if (!document.fullscreenElement) {
    if (videoPlayer.requestFullscreen) {
      videoPlayer.requestFullscreen();
    } else if (videoPlayer.webkitRequestFullscreen) {
      videoPlayer.webkitRequestFullscreen();
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  }
}

// ==========================================
// Audio Player Controls & Logic
// ==========================================
async function playAudio(fileSubpath, filename) {
  if (currentPlayingSubpath === fileSubpath && !audio.error) {
    togglePlayPause();
    return;
  }

  currentPlayingSubpath = fileSubpath;
  highlightPlayingFile();

  const isWma = filename.toLowerCase().endsWith('.wma');
  playerTrackName.textContent = (isWma ? 'מכין שיעור WMA... ' : 'טוען... ') + filename.replace(/\.[^/.]+$/, '');
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
    try {
      await audio.play();
    } catch (playErr) {
      if (playErr.name !== 'AbortError') {
        console.warn("Audio play warning:", playErr);
      }
    }
    
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
  if (!audio.src || isNaN(audio.duration) || !isFinite(audio.duration)) return;
  audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + seconds));
}

function handleSeek(val) {
  if (!audio.src || isNaN(audio.duration) || !isFinite(audio.duration)) return;
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

  if (!currentPlayingSubpath) return;

  let activeRow = document.getElementById(`file-row-${encodeId(currentPlayingSubpath)}`);
  if (!activeRow) {
    activeRow = Array.from(document.querySelectorAll('.file-row')).find(r => r.dataset.subpath === currentPlayingSubpath);
  }

  if (activeRow) {
    activeRow.classList.add('playing');
    const btn = activeRow.querySelector('.file-action-btn span');
    const isPaused = audio.paused;
    if (btn) btn.textContent = isPaused ? 'המשך ▶' : 'השהה ⏸';
    const icon = activeRow.querySelector('.file-icon');
    if (icon) icon.textContent = isPaused ? '⏸' : '🔊';
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
  if (currentPlayingSubpath) {
    const fn = currentPlayingSubpath.split('/').pop();
    playerTrackName.textContent = fn.replace(/\.[^/.]+$/, '');
  }
});

audio.addEventListener('pause', () => {
  playIcon.textContent = '▶';
  highlightPlayingFile();
});

audio.addEventListener('timeupdate', () => {
  if (!isNaN(audio.duration) && isFinite(audio.duration) && audio.duration > 0) {
    const percent = (audio.currentTime / audio.duration) * 100;
    progressSlider.value = percent;
    currentTimeLabel.textContent = formatTime(audio.currentTime);
  } else if (!isNaN(audio.currentTime)) {
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

// Automatic Recovery on stream interrupt or token expiry
let isRecovering = false;
audio.addEventListener('error', async () => {
  console.warn("Audio playback error encountered:", audio.error);
  if (isRecovering || !currentPlayingSubpath) return;

  const savedTime = audio.currentTime || 0;
  // If failed right at the start (savedTime === 0), the file format is corrupt or conversion failed
  if (savedTime === 0) {
    playIcon.textContent = '▶';
    const isWma = currentPlayingSubpath.toLowerCase().endsWith('.wma');
    const msg = isWma
      ? "לא ניתן לנגן קובץ WMA זה (ייתכן שהקובץ פגום או מוגן בזכויות יוצרים DRM)."
      : "שגיאה בטעינת השיעור או שהקובץ אינו נתמך.";
    playerTrackName.textContent = '⚠️ ' + msg;
    alert(msg);
    return;
  }

  isRecovering = true;
  try {
    const tokenRes = await fetch(`/api/rav-tzvi/token?file=${encodeURIComponent(currentPlayingSubpath)}`, { method: 'POST' });
    if (tokenRes.ok) {
      const tokenData = await tokenRes.json();
      audio.src = `/api/rav-tzvi/stream?file=${encodeURIComponent(currentPlayingSubpath)}&token=${tokenData.token}`;
      audio.addEventListener('canplay', function onCanPlay() {
        audio.removeEventListener('canplay', onCanPlay);
        if (savedTime > 0) audio.currentTime = savedTime;
        audio.play().catch(() => {});
      });
      audio.load();
    }
  } catch (err) {
    console.error("Audio recovery failed:", err);
  } finally {
    setTimeout(() => { isRecovering = false; }, 1500);
  }
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
    return true;
  } else {
    // If no element in that direction (e.g., in files list or at borders), seek audio
    if (direction === 'right' && audio.src) {
      seekRelative(10);
      return true;
    } else if (direction === 'left' && audio.src) {
      seekRelative(-10);
      return true;
    }
    return false;
  }
}

document.addEventListener('contextmenu', e => e.preventDefault());
document.addEventListener('copy', e => {
  if (docModal && docModal.style.display !== 'none') {
    e.preventDefault();
    showProtectionToast('🔒 העתקת תוכן חסומה להגנה על זכויות יוצרים');
  }
});
document.addEventListener('cut', e => {
  if (docModal && docModal.style.display !== 'none') {
    e.preventDefault();
    showProtectionToast('🔒 העתקת תוכן חסומה להגנה על זכויות יוצרים');
  }
});

document.addEventListener('keydown', e => {
  // Block browser save, print, and source shortcuts
  if (e.ctrlKey || e.metaKey) {
    const k = e.key.toLowerCase();
    if (['s', 'u', 'p'].includes(k)) {
      e.preventDefault();
      showProtectionToast('🔒 שמירה והדפסה חסומות להגנה על זכויות יוצרים');
      return;
    }
    if (docModal && docModal.style.display !== 'none') {
      if (['c', 'a', 'x'].includes(k)) {
        e.preventDefault();
        showProtectionToast('🔒 העתקת תוכן חסומה להגנה על זכויות יוצרים');
        return;
      }
    }
  }

  const isInputFocused = e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT';

  // Quick search shortcut: '/' or 'Ctrl+F'
  if (!isInputFocused && (e.key === '/' || (e.ctrlKey && (e.key === 'f' || e.key === 'F')))) {
    e.preventDefault();
    searchInput.focus();
    searchInput.select();
    return;
  }

  // Escape: close modal, exit search or navigate back
  if (e.key === 'Escape') {
    if (docModal && docModal.style.display !== 'none') {
      e.preventDefault();
      closeDocViewer();
      return;
    }
    if (videoModal && videoModal.style.display !== 'none') {
      e.preventDefault();
      closeVideoPlayer();
      return;
    }
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
    if (moveSpatial('down')) e.preventDefault();
    return;
  }
  if (e.code === 'ArrowUp') {
    if (moveSpatial('up')) e.preventDefault();
    return;
  }
  if (e.code === 'ArrowRight') {
    if (moveSpatial('right')) e.preventDefault();
    return;
  }
  if (e.code === 'ArrowLeft') {
    if (moveSpatial('left')) e.preventDefault();
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

  // Spacebar to play/pause audio or video
  if (e.code === 'Space') {
    e.preventDefault();
    if (videoModal && videoModal.style.display !== 'none' && videoPlayer) {
      if (videoPlayer.paused) videoPlayer.play(); else videoPlayer.pause();
      return;
    }
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

// Initialize on page load (or immediately if DOM is already ready)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    loadFolder('');
  });
} else {
  loadFolder('');
}
