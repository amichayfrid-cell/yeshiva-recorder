// Student Note Submission Logic

document.addEventListener('DOMContentLoaded', () => {
  const urlParams = new URLSearchParams(window.location.search);
  const rawFileParam = urlParams.get('file') || '';
  
  // Extract filename only (handles full Windows path or unix path)
  let cleanFilename = rawFileParam;
  if (cleanFilename.includes('\\')) {
    cleanFilename = cleanFilename.split('\\').pop();
  } else if (cleanFilename.includes('/')) {
    cleanFilename = cleanFilename.split('/').pop();
  }

  const displayFilenameEl = document.getElementById('displayFilename');
  const noteForm = document.getElementById('noteForm');
  const noteContentEl = document.getElementById('noteContent');
  const submitBtn = document.getElementById('submitBtn');
  const spinner = document.getElementById('spinner');
  const formView = document.getElementById('formView');
  const successView = document.getElementById('successView');

  if (cleanFilename) {
    displayFilenameEl.textContent = cleanFilename;
  } else {
    displayFilenameEl.textContent = 'לא צוין שם קובץ ספציפי (הערה כללית)';
  }

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

  noteForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const content = noteContentEl.value.trim();
    if (!content) return;

    submitBtn.disabled = true;
    spinner.style.display = 'inline-block';

    try {
      const response = await fetch('/api/notes', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filename: cleanFilename || 'general_note',
          content: content,
          filepath: rawFileParam,
        }),
      });

      if (!response.ok) {
        throw new Error('שגיאה בשליחת ההערה');
      }

      formView.style.display = 'none';
      successView.style.display = 'block';
    } catch (err) {
      showToast(err.message || 'שגיאה בשליחת ההערה. אנא נסה שוב.', 'error');
      submitBtn.disabled = false;
      spinner.style.display = 'none';
    }
  });
});
