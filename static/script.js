// ---- CTA Upload ----

let ctaUploaded = false;

function onDragOver(e) {
  e.preventDefault();
  document.getElementById('cta-drop').classList.add('dragging');
}
function onDragLeave(e) {
  document.getElementById('cta-drop').classList.remove('dragging');
}
function onDropCTA(e) {
  e.preventDefault();
  onDragLeave(e);
  const file = e.dataTransfer.files[0];
  if (file) handleCTAFile(file);
}

function handleCTAFile(file) {
  if (!file || !file.type.startsWith('video/')) {
    setCTAStatus('Please select a valid video file.', 'error');
    return;
  }
  const wrap = document.getElementById('cta-progress-wrap');
  const bar = document.getElementById('cta-progress-bar');
  const label = document.getElementById('cta-label');
  wrap.style.display = 'block';
  bar.style.width = '0%';

  const formData = new FormData();
  formData.append('cta', file);

  const xhr = new XMLHttpRequest();
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      bar.style.width = Math.round((e.loaded / e.total) * 100) + '%';
    }
  };
  xhr.onload = () => {
    wrap.style.display = 'none';
    if (xhr.status === 200) {
      const data = JSON.parse(xhr.responseText);
      label.innerHTML = `✅ <strong>${file.name}</strong> uploaded`;
      setCTAStatus(`CTA ready — ${formatFileSize(file.size)}`, 'success');
      ctaUploaded = true;
    } else {
      setCTAStatus('Upload failed. Try again.', 'error');
    }
  };
  xhr.onerror = () => {
    wrap.style.display = 'none';
    setCTAStatus('Network error during upload.', 'error');
  };
  xhr.open('POST', '/upload-cta');
  xhr.send(formData);
}

function setCTAStatus(msg, type) {
  const el = document.getElementById('cta-status');
  el.textContent = msg;
  el.className = 'cta-status ' + (type || '');
}

function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ---- URL Counter ----

document.addEventListener('DOMContentLoaded', () => {
  const textarea = document.getElementById('url-input');
  textarea.addEventListener('input', updateURLCount);
  updateURLCount();
});

function updateURLCount() {
  const lines = getURLs();
  const el = document.getElementById('url-count');
  el.textContent = lines.length === 0 ? '0 URLs' : `${lines.length} URL${lines.length > 1 ? 's' : ''}`;
}

function getURLs() {
  return document.getElementById('url-input').value
    .split('\n')
    .map(l => l.trim())
    .filter(l => l.length > 0);
}

// ---- Processing ----

let pollInterval = null;

async function startProcessing() {
  if (!ctaUploaded) {
    alert('Please upload your CTA video first (Step 1).');
    return;
  }
  const urls = getURLs();
  if (urls.length === 0) {
    alert('Please paste at least one YouTube Shorts URL (Step 2).');
    return;
  }

  const btn = document.getElementById('btn-process');
  const btnText = document.getElementById('btn-text');
  btn.disabled = true;
  btnText.textContent = 'Starting…';

  try {
    const res = await fetch('/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ urls })
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error || 'Error starting job.');
      btn.disabled = false;
      btnText.textContent = 'Generate Clips';
      return;
    }
    btnText.textContent = 'Processing…';
    startPolling(data.job_id);
  } catch (e) {
    alert('Failed to connect to server.');
    btn.disabled = false;
    btnText.textContent = 'Generate Clips';
  }
}

function startPolling(jobId) {
  const jobSection = document.getElementById('job-section');
  const jobIdLabel = document.getElementById('job-id-label');
  jobSection.style.display = 'block';
  jobIdLabel.textContent = `job: ${jobId.slice(0, 8)}`;

  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(() => pollStatus(jobId), 1000);
  pollStatus(jobId); // immediate first call
}

async function pollStatus(jobId) {
  try {
    const res = await fetch(`/status/${jobId}`);
    const data = await res.json();
    renderResults(data.results);
    updateJobSummary(data.results, data.status, jobId);

    if (data.status === 'done') {
      clearInterval(pollInterval);
      document.getElementById('btn-process').disabled = false;
      document.getElementById('btn-text').textContent = 'Generate More Clips';
      loadOutputFiles();
    }
  } catch (e) {
    // silent fail, keep polling
  }
}

// ---- Status rendering ----

const STATUS_LABELS = {
  queued: 'Queued',
  downloading: 'Downloading…',
  trimming: 'Trimming to 3s…',
  encoding_cta: 'Encoding CTA…',
  concatenating: 'Stitching…',
  done: '✅ Done',
  error: '❌ Error'
};

const STATUS_PROGRESS = {
  queued: 0,
  downloading: 25,
  trimming: 55,
  encoding_cta: 75,
  concatenating: 90,
  done: 100,
  error: 100
};

const STATUS_COLORS = {
  queued: 'rgba(148,163,184,0.4)',
  downloading: '#fbbf24',
  trimming: '#06b6d4',
  encoding_cta: '#8b5cf6',
  concatenating: '#8b5cf6',
  done: '#10b981',
  error: '#f43f5e'
};

function renderResults(results) {
  const container = document.getElementById('url-results');

  results.forEach((item, idx) => {
    let el = document.getElementById(`url-item-${idx}`);
    if (!el) {
      el = document.createElement('div');
      el.id = `url-item-${idx}`;
      el.className = 'url-item';
      el.innerHTML = `
        <div class="url-item-top">
          <span class="url-item-url" title="${item.url}">${item.url}</span>
          <span class="url-item-status status-queued" id="status-badge-${idx}">Queued</span>
        </div>
        <div class="url-item-bar">
          <div class="url-item-fill" id="status-fill-${idx}"></div>
        </div>
        <div class="url-item-extra" id="extra-${idx}"></div>
      `;
      container.appendChild(el);
    }

    const badge = document.getElementById(`status-badge-${idx}`);
    const fill = document.getElementById(`status-fill-${idx}`);
    const extra = document.getElementById(`extra-${idx}`);
    const s = item.status;

    badge.textContent = STATUS_LABELS[s] || s;
    badge.className = `url-item-status status-${s}`;
    el.className = `url-item ${s === 'done' ? 'done' : s === 'error' ? 'error' : ''}`;

    const pct = STATUS_PROGRESS[s] || 0;
    fill.style.width = pct + '%';
    fill.style.background = STATUS_COLORS[s] || '#8b5cf6';

    if (s === 'done' && item.filename) {
      extra.innerHTML = `<a class="url-item-download" href="/download/${item.filename}" download>⬇ Download ${item.filename}</a>`;
    } else if (s === 'error' && item.error) {
      extra.innerHTML = `<div class="url-item-error">${item.error}</div>`;
    } else {
      extra.innerHTML = '';
    }
  });
}

function updateJobSummary(results, jobStatus, jobId) {
  const done = results.filter(r => r.status === 'done').length;
  const errors = results.filter(r => r.status === 'error').length;
  const total = results.length;
  const el = document.getElementById('job-summary');
  const batchDownloadEl = document.getElementById('job-download-batch');

  if (jobStatus === 'done') {
    el.textContent = `✅ Finished — ${done}/${total} clips ready${errors > 0 ? `, ${errors} error(s)` : ''}`;
    if (done > 0 && jobId) {
      batchDownloadEl.innerHTML = `<a class="btn-download" href="/download-all?job_id=${jobId}" download>⬇ Download Batch</a>`;
    }
  } else {
    el.textContent = `Processing ${total} clip${total > 1 ? 's' : ''}… (${done} done, ${errors} error${errors !== 1 ? 's' : ''})`;
    batchDownloadEl.innerHTML = '';
  }
}

// ---- Output file listing ----

async function loadOutputFiles() {
  const res = await fetch('/files');
  const data = await res.json();
  const section = document.getElementById('output-section');
  const list = document.getElementById('output-list');

  if (!data.files || data.files.length === 0) {
    section.style.display = 'none';
    return;
  }

  section.style.display = 'block';
  list.innerHTML = data.files.map(f => `
    <div class="output-file">
      <span class="output-file-name">🎬 ${f}</span>
      <a class="btn-download" href="/download/${f}" download>⬇ Download</a>
    </div>
  `).join('');
}

async function clearOutput() {
  if (!confirm('Delete all output clips?')) return;
  await fetch('/clear-output', { method: 'POST' });
  document.getElementById('output-section').style.display = 'none';
}

// Load existing output files on page load
loadOutputFiles();
