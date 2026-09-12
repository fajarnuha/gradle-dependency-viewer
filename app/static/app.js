// The app is stateless: nothing is stored on the server. Pre-compiled projects are served as
// static files, and an ad-hoc upload is parsed on the fly and kept only in this tab's
// sessionStorage so that the viewers (and the back button) can reach it.
const UPLOAD_KEY = 'gdv:upload';
const CURRENT_KEY = 'gdv:current';
const PREVIEW_LIMIT = 200000;

const fileInput = document.getElementById('txt-file');
const dropZone = document.getElementById('drop-zone');
const errorEl = document.getElementById('upload-error');
const welcomeState = document.getElementById('welcome-state');
const processingState = document.getElementById('processing-state');
const readyState = document.getElementById('ready-state');
const txtPreview = document.getElementById('txt-preview');
const jsonPreview = document.getElementById('json-preview');
const openGraphBtn = document.getElementById('open-graph-btn');
const openTreeBtn = document.getElementById('open-tree-btn');
const enlistBtn = document.getElementById('enlist-btn');
const currentFileName = document.getElementById('current-file-name');
const sourceBadge = document.getElementById('source-badge');
const txtPanel = document.getElementById('txt-panel');
const resultsGrid = document.querySelector('.results-grid');
const sampleList = document.getElementById('sample-list');
const filterInput = document.getElementById('filter-text');
const projectOnlyCheckbox = document.getElementById('project-only');

let samples = [];
// { kind: 'sample', filename, name, data } or { kind: 'upload', name, data, txt }
let current = null;

function setState(state) {
  welcomeState.classList.toggle('hidden', state !== 'welcome');
  processingState.classList.toggle('hidden', state !== 'processing');
  readyState.classList.toggle('hidden', state !== 'ready');
}

function setDisabled(disabled) {
  fileInput.disabled = disabled;
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

function readSession(key) {
  try {
    return JSON.parse(sessionStorage.getItem(key) || 'null');
  } catch (error) {
    return null;
  }
}

function writeSession(key, value) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (error) {
    console.warn(`Could not keep ${key} in sessionStorage:`, error);
    return false;
  }
}

function withoutRawTxt(data) {
  const { raw_txt, ...rest } = data || {};
  return rest;
}

function preview(text) {
  return text.length > PREVIEW_LIMIT ? `${text.slice(0, PREVIEW_LIMIT)}\n… (preview truncated)` : text;
}

// --- Pre-compiled open source projects ---

async function fetchSamples() {
  try {
    const response = await fetch('/api/samples');
    if (!response.ok) throw new Error(`Server returned ${response.status}`);
    samples = await response.json();
  } catch (error) {
    console.error('Failed to fetch samples:', error);
    samples = [];
  }
  renderSampleList();
}

function renderSampleList() {
  sampleList.replaceChildren();

  if (samples.length === 0) {
    const empty = document.createElement('li');
    empty.className = 'empty-list';
    empty.textContent = 'No pre-compiled projects available.';
    sampleList.append(empty);
    return;
  }

  samples.forEach(sample => {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'project-item';
    button.dataset.filename = sample.filename;
    button.setAttribute('aria-label', `Open ${sample.name} dependencies`);
    button.innerHTML = `
      <span class="project-icon" aria-hidden="true"></span>
      <span class="project-meta">
        <span class="project-name"></span>
        <span class="project-stats"></span>
      </span>
      <svg class="project-chevron" viewBox="0 0 24 24" width="18" height="18" stroke="currentColor"
        stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polyline points="9 18 15 12 9 6"></polyline>
      </svg>
    `;
    button.querySelector('.project-icon').textContent = sample.name.charAt(0);
    button.querySelector('.project-name').textContent = sample.name;
    button.querySelector('.project-stats').textContent =
      `${Number(sample.entries).toLocaleString()} entries · ${Number(sample.modules).toLocaleString()} modules`;
    button.addEventListener('click', () => openSample(sample));
    item.append(button);
    sampleList.append(item);
  });
  updateActiveSample();
}

function updateActiveSample() {
  sampleList.querySelectorAll('.project-item').forEach(button => {
    const active = current?.kind === 'sample' && current.filename === button.dataset.filename;
    button.setAttribute('aria-pressed', String(active));
  });
}

async function openSample(sample) {
  clearError();
  setState('processing');
  setDisabled(true);

  try {
    const response = await fetch(sample.path);
    if (!response.ok) throw new Error(`Failed to load ${sample.name}.`);
    const data = await response.json();
    showResult({ kind: 'sample', filename: sample.filename, name: sample.name, data });
    writeSession(CURRENT_KEY, { kind: 'sample', filename: sample.filename });
  } catch (error) {
    setState('welcome');
    showError(error.message);
  } finally {
    setDisabled(false);
  }
}

// --- Ad-hoc upload ---

async function handleUpload(file) {
  clearError();
  if (!file) return;

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
    const upload = { name: result.name, data: result.json, txt: result.txt };

    // Keep the upload in this tab only; drop the TXT first if the browser's quota is too small.
    const kept = writeSession(UPLOAD_KEY, upload) || writeSession(UPLOAD_KEY, { name: upload.name, data: upload.data });
    writeSession(CURRENT_KEY, { kind: 'upload' });
    showResult({ kind: 'upload', ...upload });
    if (!kept) {
      showError('This file is too large to keep in the browser tab, so the viewers may not be able to open it.');
    }
  } catch (error) {
    setState('welcome');
    showError(error.message);
  } finally {
    setDisabled(false);
    fileInput.value = '';
  }
}

// --- Result view ---

function showResult(entry) {
  current = entry;
  currentFileName.textContent = entry.name;
  sourceBadge.textContent = entry.kind === 'sample'
    ? 'Pre-compiled open source project'
    : 'Your upload · kept in this browser tab only';
  sourceBadge.classList.toggle('upload', entry.kind === 'upload');

  jsonPreview.textContent = preview(JSON.stringify(withoutRawTxt(entry.data), null, 2));
  const txt = entry.txt || '';
  txtPreview.textContent = preview(txt);
  txtPanel.classList.toggle('hidden', !txt);
  resultsGrid.classList.toggle('single-column', !txt);

  updateActiveSample();
  setState('ready');
}

function viewerUrl(viewer) {
  const params = new URLSearchParams();
  if (current.kind === 'sample') {
    params.set('sample', current.filename);
  } else {
    params.set('source', 'upload');
  }

  const filterValue = filterInput.value.trim();
  if (filterValue) {
    params.set('filter', filterValue);
  }
  if (projectOnlyCheckbox.checked) {
    params.set('project_only', 'true');
  }
  return `/viz/${viewer}.html?${params}`;
}

openGraphBtn.addEventListener('click', () => {
  if (current) window.location.href = viewerUrl('graph_viewer');
});

openTreeBtn.addEventListener('click', () => {
  if (current) window.location.href = viewerUrl('tree_viewer');
});

enlistBtn.addEventListener('click', async () => {
  if (!current) return;
  clearError();
  try {
    const response = await fetch('/api/enlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: withoutRawTxt(current.data) })
    });
    if (!response.ok) throw new Error('Failed to enlist dependencies.');

    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = `${current.name}_dependencies.yaml`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    showError(error.message);
  }
});

// Restore what this tab was showing (e.g. after coming back from a viewer).
async function restoreCurrent() {
  const saved = readSession(CURRENT_KEY);
  if (saved?.kind === 'upload') {
    const upload = readSession(UPLOAD_KEY);
    if (upload?.data) {
      showResult({ kind: 'upload', ...upload });
      return;
    }
  } else if (saved?.kind === 'sample') {
    const sample = samples.find(s => s.filename === saved.filename);
    if (sample) {
      await openSample(sample);
      return;
    }
  }
  setState('welcome');
}

// --- Drop zone ---

fileInput.addEventListener('change', () => {
  if (fileInput.files.length) {
    handleUpload(fileInput.files[0]);
  }
});

dropZone.addEventListener('click', () => {
  fileInput.click();
});

dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    fileInput.click();
  }
});

['dragover', 'dragleave', 'dragend'].forEach(type => {
  dropZone.addEventListener(type, (e) => {
    e.preventDefault();
    if (type === 'dragover') {
      dropZone.classList.add('drop-zone--over');
    } else {
      dropZone.classList.remove('drop-zone--over');
    }
  });
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drop-zone--over');

  if (e.dataTransfer.files.length) {
    handleUpload(e.dataTransfer.files[0]);
  }
});

// Copy hint command
const copyHintBtn = document.getElementById('copy-hint-btn');
const hintCode = document.getElementById('hint-code');

if (copyHintBtn && hintCode) {
  copyHintBtn.addEventListener('click', () => {
    const text = hintCode.textContent;
    navigator.clipboard.writeText(text).then(() => {
      const originalIcon = copyHintBtn.innerHTML;
      copyHintBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none"
          stroke-linecap="round" stroke-linejoin="round" style="color: #10b981;">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      `;
      setTimeout(() => {
        copyHintBtn.innerHTML = originalIcon;
      }, 2000);
    });
  });
}

// Initial load
setState('welcome');
fetchSamples().then(restoreCurrent);
