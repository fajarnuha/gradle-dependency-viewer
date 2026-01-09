const uploadForm = document.getElementById('upload-form');
const fileInput = document.getElementById('txt-file');
const errorEl = document.getElementById('upload-error');
const uploadState = document.getElementById('upload-state');
const processingState = document.getElementById('processing-state');
const readyState = document.getElementById('ready-state');
const txtPreview = document.getElementById('txt-preview');
const jsonPreview = document.getElementById('json-preview');
const vizButtons = document.querySelectorAll('[data-viz]');

function setState(state) {
  uploadState.classList.toggle('hidden', state !== 'upload');
  processingState.classList.toggle('hidden', state !== 'processing');
  readyState.classList.toggle('hidden', state !== 'ready');
}

function setDisabled(disabled) {
  fileInput.disabled = disabled;
  uploadForm.querySelector('button[type="submit"]').disabled = disabled;
}

function showError(message) {
  errorEl.textContent = message;
}

function clearError() {
  errorEl.textContent = '';
}

function isTxtFile(file) {
  return file && file.name.toLowerCase().endsWith('.txt');
}

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError();

  const file = fileInput.files[0];
  if (!file) {
    showError('Please choose a TXT file to upload.');
    return;
  }
  if (!isTxtFile(file)) {
    showError('Only .txt files are supported.');
    return;
  }

  setState('processing');
  setDisabled(true);

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || 'Upload failed. Please try again.');
    }

    const result = await response.json();
    const prettyJson = JSON.stringify(result.json, null, 2);

    localStorage.setItem('last_result_json', JSON.stringify(result.json));
    localStorage.setItem('last_uploaded_txt', result.txt || '');

    txtPreview.textContent = result.txt || '';
    jsonPreview.textContent = prettyJson;

    setState('ready');
  } catch (error) {
    setState('upload');
    showError(error.message);
  } finally {
    setDisabled(false);
  }
});

vizButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const target = button.getAttribute('data-viz');
    if (target) {
      window.location.href = target;
    }
  });
});
