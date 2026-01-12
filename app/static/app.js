const uploadForm = document.getElementById('upload-form');
const fileInput = document.getElementById('txt-file');
const dropZone = document.getElementById('drop-zone');
const errorEl = document.getElementById('upload-error');
const welcomeState = document.getElementById('welcome-state');
const processingState = document.getElementById('processing-state');
const readyState = document.getElementById('ready-state');
const txtPreview = document.getElementById('txt-preview');
const jsonPreview = document.getElementById('json-preview');
const fileList = document.getElementById('file-list');
const openGraphBtn = document.getElementById('open-graph-btn');
const openTreeBtn = document.getElementById('open-tree-btn');
const enlistBtn = document.getElementById('enlist-btn');
const currentFileName = document.getElementById('current-file-name');
const txtPanel = document.getElementById('txt-panel');
const resultsGrid = document.querySelector('.results-grid');

let selectedFile = null;

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

async function fetchFiles() {
  try {
    const response = await fetch('/api/files');
    const files = await response.json();
    renderFileList(files);
  } catch (error) {
    console.error('Failed to fetch files:', error);
  }
}

function renderFileList(files) {
  if (files.length === 0) {
    fileList.innerHTML = '<li class="empty-list">No past files found.</li>';
    return;
  }

  fileList.innerHTML = files.map(file => `
    <li class="file-item ${selectedFile === file.name ? 'active' : ''}" data-name="${file.name}">
      <span class="file-name" title="${file.name}">${file.name}</span>
      <div class="file-actions">
        <button class="delete-btn" onclick="deleteFile(event, '${file.name}')" title="Delete file">×</button>
      </div>
    </li>
  `).join('');

  fileList.querySelectorAll('.file-item').forEach(item => {
    item.addEventListener('click', () => selectFile(item.dataset.name));
  });
}

async function selectFile(filename) {
  selectedFile = filename;
  renderFileList(await (await fetch('/api/files')).json());

  // Fetch file content to preview
  try {
    const response = await fetch(`/static/data/${filename}`);
    const data = await response.json();

    currentFileName.textContent = filename;
    jsonPreview.textContent = JSON.stringify(data, null, 2);
    txtPreview.textContent = data.raw_txt || "Original TXT content not available for this file.";

    // Hide TXT and arrow panels for a cleaner view
    txtPanel.classList.add('hidden');
    resultsGrid.classList.add('single-column');

    openGraphBtn.onclick = () => {
      window.location.href = `/viz/graph_viewer.html?file=${filename}`;
    };

    openTreeBtn.onclick = () => {
      window.location.href = `/viz/tree_viewer.html?file=${filename}`;
    };

    enlistBtn.onclick = () => {
      window.location.href = `/api/enlist/${filename}`;
    };

    setState('ready');
  } catch (error) {
    console.error('Failed to load file content:', error);
  }
}

async function deleteFile(event, filename) {
  event.stopPropagation();
  if (!confirm(`Are you sure you want to delete ${filename}?`)) return;

  try {
    const response = await fetch(`/api/files/${filename}`, { method: 'DELETE' });
    if (response.ok) {
      if (selectedFile === filename) {
        selectedFile = null;
        setState('welcome');
      }
      fetchFiles();
    }
  } catch (error) {
    console.error('Failed to delete file:', error);
  }
}

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
    fetchFiles();
    selectFile(result.filename);
  } catch (error) {
    setState('welcome');
    showError(error.message);
  } finally {
    setDisabled(false);
  }
}

fileInput.addEventListener('change', () => {
  if (fileInput.files.length) {
    handleUpload(fileInput.files[0]);
  }
});

dropZone.addEventListener('click', () => {
  fileInput.click();
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
    fileInput.files = e.dataTransfer.files;
    handleUpload(e.dataTransfer.files[0]);
  }
});

// Initial load
fetchFiles();
setState('welcome');
