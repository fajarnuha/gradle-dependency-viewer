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
    
    // Restore selected file from local storage if available
    const storedFile = localStorage.getItem('selectedFile');
    if (storedFile && files.some(f => f.name === storedFile)) {
        selectedFile = storedFile;
        // Don't auto-select/fetch content yet, just highlight in list
        // Or if we want to restore the view state, we'd call selectFile(storedFile)
        // But let's just highlight it for now to match typical "back" behavior logic or fully restore
        // The prompt implies "state ... is gone", so let's fully restore if present.
        selectFile(storedFile); 
    } else {
        renderFileList(files);
    }
  } catch (error) {
    console.error('Failed to fetch files:', error);
  }
}

function renderFileList(files) {
  if (!fileList) return;

  if (files.length === 0) {
    fileList.innerHTML = '<li class="empty-list">No past files found.</li>';
    return;
  }

  fileList.innerHTML = files.map(file => `
    <li class="file-item ${selectedFile === file.name ? 'active' : ''}" data-name="${file.name}">
      <span class="file-name" title="${file.name}">${file.name}</span>
      <div class="file-actions">
        <button class="delete-btn" onclick="deleteFile(event, '${file.name}')" aria-label="Delete ${file.name}">
          <span aria-hidden="true">×</span>
        </button>
      </div>
    </li>
  `).join('');

  fileList.querySelectorAll('.file-item').forEach(item => {
    item.addEventListener('click', () => selectFile(item.dataset.name));
  });
}

async function selectFile(filename) {
  selectedFile = filename;
  localStorage.setItem('selectedFile', filename);
  
  try {
    const filesResponse = await fetch('/api/files');
    const files = await filesResponse.json();
    renderFileList(files);

    // Fetch file content to preview
    const response = await fetch(`/static/data/${filename}`);
    if (!response.ok) throw new Error('File fetch failed');
    const data = await response.json();

    currentFileName.textContent = filename;
    jsonPreview.textContent = JSON.stringify(data, null, 2);
    txtPreview.textContent = data.raw_txt || "Original TXT content not available for this file.";

    // Hide TXT and arrow panels for a cleaner view
    txtPanel.classList.add('hidden');
    resultsGrid.classList.add('single-column');

    // Filter elements
    const filterInput = document.getElementById('filter-text');
    const projectOnlyCheckbox = document.getElementById('project-only');

    const handleVizClick = (targetUrlConstructor) => {
      const filterValue = filterInput.value.trim();
      const projectOnly = projectOnlyCheckbox.checked;

      let url = targetUrlConstructor(filename);
      const params = new URLSearchParams();

      if (filterValue) {
        params.append('filter', filterValue);
      }
      if (projectOnly) {
        params.append('project_only', 'true');
      }

      const queryString = params.toString();
      if (queryString) {
        url += (url.includes('?') ? '&' : '?') + queryString;
      }

      window.location.href = url;
    };

    openGraphBtn.onclick = () => handleVizClick((f) => `/viz/graph_viewer.html?file=${f}`);
    openTreeBtn.onclick = () => handleVizClick((f) => `/viz/tree_viewer.html?file=${f}`);

    enlistBtn.onclick = () => {
      window.location.href = `/api/enlist/${filename}`;
    };

    setState('ready');
  } catch (error) {
    console.error('Failed to load file content:', error);
    // If we fail here, we should probably go back to welcome or show error
    // If called from handleUpload, the error will be caught there.
    throw error;
  }
}

async function deleteFile(event, filename) {
  event.stopPropagation();
  if (!confirm(`Are you sure you want to delete ${filename}?`)) return;

  const btn = event.target.closest('button');
  const originalContent = btn ? btn.innerHTML : '';

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-sm" aria-hidden="true"></span><span class="sr-only">Deleting...</span>';
  }

  try {
    const response = await fetch(`/api/files/${filename}`, { method: 'DELETE' });
    if (response.ok) {
      if (selectedFile === filename) {
        selectedFile = null;
        localStorage.removeItem('selectedFile');
        setState('welcome');
      }
      fetchFiles();
    } else {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalContent;
      }
    }
  } catch (error) {
    console.error('Failed to delete file:', error);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalContent;
    }
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
    await fetchFiles();
    await selectFile(result.filename);
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
    fileInput.files = e.dataTransfer.files;
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
fetchFiles();
fetchSamples();
setState('welcome');

// Sample logic
const sampleSection = document.getElementById('sample-section');
const sampleList = document.getElementById('sample-list');

async function fetchSamples() {
  try {
    const response = await fetch('/api/samples');
    const samples = await response.json();
    renderSampleList(samples);
  } catch (error) {
    console.error('Failed to fetch samples:', error);
  }
}

function renderSampleList(samples) {
  if (samples.length === 0) {
    sampleSection.classList.add('hidden');
    return;
  }

  sampleSection.classList.remove('hidden');
  sampleList.innerHTML = samples.map(sample => `
    <button class="sample-chip" onclick="handleSampleClick('${sample.filename}')">
      ${sample.name}
    </button>
  `).join('');
}

async function handleSampleClick(filename) {
  clearError();
  setState('processing');
  setDisabled(true);

  try {
    const response = await fetch(`/api/samples/${filename}/process`, {
      method: 'POST'
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || 'Failed to process sample.');
    }

    const result = await response.json();
    await fetchFiles();
    await selectFile(result.filename);
  } catch (error) {
    setState('welcome');
    showError(error.message);
  } finally {
    setDisabled(false);
  }
}
