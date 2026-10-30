/**
 * Global Security & DevTools Protection Guard
 * Blocks F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C, Ctrl+Shift+K,
 * Ctrl+U (view source), Ctrl+S (save page), Ctrl+P (print),
 * and right-click context menu across the entire website.
 */
(function() {
  function showGuardToast(msg) {
    let toast = document.getElementById('securityGuardToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'securityGuardToast';
      toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(15, 23, 42, 0.95);
        color: #ffffff;
        padding: 12px 24px;
        border-radius: 24px;
        font-size: 14px;
        font-weight: 600;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        z-index: 999999;
        pointer-events: none;
        direction: rtl;
        font-family: 'Rubik', 'Assistant', sans-serif;
        border: 1px solid rgba(255, 255, 255, 0.2);
        transition: opacity 0.2s ease;
      `;
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.display = 'block';
    toast.style.opacity = '1';
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => { toast.style.display = 'none'; }, 200);
    }, 2500);
  }

  // 1. Block right-click context menu everywhere
  document.addEventListener('contextmenu', function(e) {
    e.preventDefault();
  }, true);

  // 2. Block developer tools and inspecting shortcuts
  window.addEventListener('keydown', function(e) {
    // Block F12 (Developer Tools)
    if (e.key === 'F12' || e.keyCode === 123) {
      e.preventDefault();
      e.stopPropagation();
      showGuardToast('🔒 פתיחת כלי פיתוח (F12) חסומה להגנה על זכויות יוצרים');
      return;
    }

    // Block Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C, Ctrl+Shift+K (DevTools inspect/console)
    if ((e.ctrlKey || e.metaKey) && e.shiftKey) {
      const k = e.key.toLowerCase();
      if (['i', 'j', 'c', 'k'].includes(k)) {
        e.preventDefault();
        e.stopPropagation();
        showGuardToast('🔒 פתיחת כלי פיתוח (Ctrl+Shift+I) חסומה להגנה על זכויות יוצרים');
        return;
      }
    }

    // Block Ctrl+U (View Source), Ctrl+S (Save Page), Ctrl+P (Print)
    if (e.ctrlKey || e.metaKey) {
      const k = e.key.toLowerCase();
      if (k === 'u') {
        e.preventDefault();
        e.stopPropagation();
        showGuardToast('🔒 הצגת קוד המקור (Ctrl+U) חסומה להגנה על זכויות יוצרים');
        return;
      }
      if (k === 's') {
        e.preventDefault();
        e.stopPropagation();
        showGuardToast('🔒 שמירת הדף חסומה להגנה על זכויות יוצרים');
        return;
      }
      if (k === 'p') {
        e.preventDefault();
        e.stopPropagation();
        showGuardToast('🔒 הדפסה חסומה להגנה על זכויות יוצרים');
        return;
      }
    }
  }, true);
})();
