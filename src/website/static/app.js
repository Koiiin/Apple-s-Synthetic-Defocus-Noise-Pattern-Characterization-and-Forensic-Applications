/* ============================================================
   SDNP Forensic Analyzer — Frontend SPA
   ============================================================ */

'use strict';

// ── State ──────────────────────────────────────────────────
let selectedFile = null;
let lastResult   = null;

// ── DOM refs ───────────────────────────────────────────────
const $  = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

// ── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initStatus();
  initUpload();
  initTabs();
  initResultsActions();
});

// ── Server status ──────────────────────────────────────────
async function initStatus() {
  const dot  = document.querySelector('.status-dot');
  const text = $('status-text');
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    if (d.bp_loaded) {
      dot.className  = 'status-dot ok';
      text.textContent = `${d.bp_count} BP variants loaded · β = ${d.beta}`;
    } else {
      dot.className  = 'status-dot err';
      text.textContent = 'BP patterns not found — check data/bp/';
    }
  } catch {
    dot.className  = 'status-dot err';
    text.textContent = 'Server unreachable';
  }
}

// ── Upload / file select ───────────────────────────────────
function initUpload() {
  const dropZone   = $('drop-zone');
  const fileInput  = $('file-input');
  const browseLink = $('browse-link');

  // Click the hidden input when the link or drop zone is clicked
  browseLink.addEventListener('click', e => { e.stopPropagation(); fileInput.click(); });
  dropZone.addEventListener('click', () => fileInput.click());

  // Drag-and-drop
  dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) handleFileSelect(fileInput.files[0]);
  });

  $('btn-clear').addEventListener('click', clearFile);
  $('btn-analyze').addEventListener('click', startAnalysis);
}

function handleFileSelect(file) {
  const allowed = ['image/jpeg', 'image/heic', 'image/heif', 'image/png'];
  const extOk   = /\.(jpe?g|heic|heif|png)$/i.test(file.name);
  if (!extOk && !allowed.includes(file.type)) {
    showToast('Định dạng không hỗ trợ. Vui lòng chọn JPEG, HEIC, hoặc PNG.');
    return;
  }

  selectedFile = file;
  $('pm-name').textContent = file.name;
  $('pm-size').textContent = formatBytes(file.size);
  $('pm-type').textContent = file.type || file.name.split('.').pop().toUpperCase();

  // Preview (browsers can't decode HEIC natively — show placeholder)
  const img = $('preview-img');
  if (file.type === 'image/heic' || file.type === 'image/heif' || /\.heic$/i.test(file.name)) {
    img.src = '';
    img.style.display = 'none';
    img.parentElement.style.background = '#21262d';
    img.parentElement.innerHTML = '<div style="height:160px;display:flex;align-items:center;justify-content:center;color:#484f58;font-size:.8rem">HEIC preview<br>not available</div>';
  } else {
    img.style.display = 'block';
    img.src = URL.createObjectURL(file);
  }

  $('preview-card').classList.remove('hidden');
}

function clearFile() {
  selectedFile = null;
  $('file-input').value = '';
  $('preview-card').classList.add('hidden');
  // Restore preview img
  const img = $('preview-img');
  img.src = '';
  img.style.display = 'block';
  img.parentElement.style.background = '';
  const thumbDiv = img.parentElement.querySelector('div');
  if (thumbDiv) thumbDiv.remove();
}

// ── Analysis flow ──────────────────────────────────────────
async function startAnalysis() {
  if (!selectedFile) return;

  showSection('sec-processing');
  const stepIds = ['ps-upload','ps-hash','ps-exif','ps-bp','ps-loc','ps-rep'];
  const delays  = [0, 400, 900, 1500, 3000, 5000]; // ms; just UI animation

  // Animate processing steps while we wait for the real response
  let stepTimer = stepIds.map((id, i) => setTimeout(() => activateStep(id), delays[i]));

  const form = new FormData();
  form.append('file', selectedFile);

  try {
    const resp = await fetch('/api/analyze', { method: 'POST', body: form });
    stepTimer.forEach(clearTimeout);

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      showSection('sec-upload');
      showToast(`Lỗi ${resp.status}: ${err.detail || 'Unknown error'}`);
      return;
    }

    const data = await resp.json();
    // Mark all steps done
    stepIds.forEach(id => { const el = $(id); el.classList.remove('active'); el.classList.add('done'); });
    await sleep(350);

    lastResult = data;
    renderResults(data);
    showSection('sec-results');

  } catch (e) {
    stepTimer.forEach(clearTimeout);
    showSection('sec-upload');
    showToast('Không kết nối được server. Kiểm tra lại uvicorn đang chạy.');
  }
}

function activateStep(id) {
  // Mark previous steps done
  const ids = ['ps-upload','ps-hash','ps-exif','ps-bp','ps-loc','ps-rep'];
  const idx  = ids.indexOf(id);
  ids.slice(0, idx).forEach(i => {
    const el = $(i); if (el) { el.classList.remove('active'); el.classList.add('done'); }
  });
  const el = $(id);
  if (el) { el.classList.remove('done'); el.classList.add('active'); }
}

// ── Render results ─────────────────────────────────────────
function renderResults(d) {
  renderVerdictBanner(d);
  renderThumbnail(d);
  renderTabOverview(d);
  renderTabExif(d);
  renderTabDetection(d);
  renderTabLocalization(d);
  renderTabReport(d);
  switchTab('overview');
}

function renderVerdictBanner(d) {
  const banner = $('verdict-banner');
  banner.className = 'verdict-banner';

  const v = d.verdict;
  let badgeText, titleText;
  if (v === 'DETECTED')     { banner.classList.add('detected');     badgeText = 'DETECTED';     titleText = 'Phát hiện dấu vết Apple Portrait Mode'; }
  else if (v === 'NOT_DETECTED') { banner.classList.add('not-detected'); badgeText = 'NOT DETECTED'; titleText = 'Không phát hiện dấu vết Portrait Mode';  }
  else                      { banner.classList.add('scale-aware');   badgeText = 'SCALE-AWARE';  titleText = 'Score-only (ảnh không ở 12MP chuẩn)'; }

  $('verdict-badge').textContent = badgeText;
  $('verdict-title').textContent = titleText;
  $('verdict-file').textContent  = d.filename || '';

  // NCC gauge
  const rho  = d.detection.rho;
  const beta = d.detection.beta;
  const max  = Math.max(beta * 2.2, rho * 1.3, 0.015);
  const rhoP = Math.min((rho / max) * 100, 100);
  const betP = Math.min((beta / max) * 100, 100);

  $('gauge-rho-val').textContent = rho.toFixed(6);
  $('gauge-fill').style.width    = rhoP.toFixed(1) + '%';
  $('gauge-threshold').style.left = betP.toFixed(1) + '%';
  $('gauge-beta-lbl').style.left  = betP.toFixed(1) + '%';
  $('gauge-beta-lbl').textContent = `β=${beta}`;
  $('gauge-max-lbl').textContent  = max.toFixed(4);
}

function renderThumbnail(d) {
  const img  = $('result-thumb');
  const meta = $('thumb-meta');
  if (d.thumbnail_url) {
    img.src = d.thumbnail_url;
    img.onclick = () => window.open(d.thumbnail_url, '_blank');
  } else {
    img.parentElement.style.display = 'none';
  }
  meta.innerHTML = `
    ${d.image_size}<br>
    ${formatBytes(d.size_bytes)}<br>
    <span style="color:var(--text-faint);font-size:.7rem">${d.timestamp.replace('T',' ').slice(0,19)} UTC</span>
  `;
}

// ── Tab: Overview ──────────────────────────────────────────
function renderTabOverview(d) {
  const det  = d.detection;
  const exif = d.exif;

  const exifBadge = exif.prediction
    ? badge('Portrait (EXIF)', 'success')
    : badge(exif.custom_rendered ? `${exif.custom_rendered}` : 'No Portrait EXIF', 'neutral');

  const bpBadge = det.detected === true
    ? badge(det.bp_info.symbol || det.bp_ref, 'success')
    : det.detected === null
    ? badge('Score only', 'warning')
    : badge('No match', 'danger');

  $('tab-overview').innerHTML = `
    <p class="section-title">Kết quả nhanh</p>
    <div class="ov-grid">
      <div class="ov-card">
        <div class="ov-card-label">BP Detection</div>
        <div class="ov-card-val">${det.rho.toFixed(6)}</div>
        <div class="ov-card-sub">ρ · threshold β = ${det.beta}</div>
      </div>
      <div class="ov-card">
        <div class="ov-card-label">Matched Pattern</div>
        <div class="ov-card-val">${bpBadge}</div>
        <div class="ov-card-sub">${det.bp_info.device || '—'} · ${det.bp_info.os || ''}</div>
      </div>
      <div class="ov-card">
        <div class="ov-card-label">EXIF Baseline</div>
        <div class="ov-card-val">${exifBadge}</div>
        <div class="ov-card-sub">CustomRendered = "${exif.custom_rendered || 'N/A'}"</div>
      </div>
      <div class="ov-card">
        <div class="ov-card-label">Processing Time</div>
        <div class="ov-card-val">${det.latency_ms} ms</div>
        <div class="ov-card-sub">${d.image_size} · ${det.filter}</div>
      </div>
    </div>
    ${det.scale_aware ? '<p class="section-title" style="margin-top:1rem">Lưu ý</p><div class="report-box" style="font-size:.82rem;color:var(--warning)">Scale-aware mode: BP đã được resize để khớp với kích thước ảnh. ρ không so sánh trực tiếp với β của paper (12MP chuẩn).</div>' : ''}
  `;
}

// ── Tab: EXIF ──────────────────────────────────────────────
function renderTabExif(d) {
  const e = d.exif;
  const cr = e.custom_rendered || '(không có)';
  const predBadge = e.prediction
    ? badge('Portrait Mode', 'success')
    : badge('Not Portrait', 'neutral');

  $('tab-exif').innerHTML = `
    <p class="section-title">EXIF Metadata</p>
    <table class="kv-table">
      <tr><td>Make</td>      <td>${e.make || '(không có)'}</td></tr>
      <tr><td>Model</td>     <td>${e.model || '(không có)'}</td></tr>
      <tr><td>CustomRendered</td><td>${cr}</td></tr>
      <tr><td>EXIF Prediction</td><td>${predBadge}</td></tr>
    </table>
    <p class="section-title">Giải thích</p>
    <div class="report-box" style="font-size:.82rem">
      Apple mã hoá Portrait Mode qua trường <code>CustomRendered</code>:<br>
      <code>8</code> = Portrait · <code>7</code> = Portrait HDR.<br>
      Trường này bị mất khi ảnh bị strip EXIF — đây là lý do cần BP detection.
    </div>
  `;
}

// ── Tab: BP Detection ──────────────────────────────────────
function renderTabDetection(d) {
  const det = d.detection;
  const rotDeg = det.rotation_deg || 'N/A';
  const hasMatch = det.bp_ref !== null;

  const statusBadge = det.detected === true
    ? badge('DETECTED', 'success')
    : det.detected === null
    ? badge('SCORE ONLY', 'warning')
    : badge('NOT DETECTED', 'danger');

  $('tab-detection').innerHTML = `
    <p class="section-title">Kết quả BP Detection</p>
    <table class="kv-table">
      <tr><td>Verdict</td>     <td>${statusBadge}</td></tr>
      <tr><td>NCC score (ρ)</td><td><strong>${det.rho.toFixed(6)}</strong></td></tr>
      <tr><td>Threshold (β)</td><td>${det.beta}</td></tr>
      <tr><td>ρ > β ?</td>    <td>${det.rho > det.beta
        ? `<span style="color:var(--success)">Yes (+${(det.rho - det.beta).toFixed(6)})</span>`
        : `<span style="color:var(--danger)">No (−${(det.beta - det.rho).toFixed(6)})</span>`}</td></tr>
    </table>

    ${hasMatch ? `
    <p class="section-title">Best Matching Pattern</p>
    <table class="kv-table">
      <tr><td>BP variant</td> <td>${det.bp_info.symbol || '—'} · <code>${det.bp_ref}</code></td></tr>
      <tr><td>Device</td>     <td>${det.bp_info.device || '—'}</td></tr>
      <tr><td>iOS</td>        <td>${det.bp_info.os || '—'}</td></tr>
      <tr><td>Rotation</td>   <td>${rotDeg} (k=${det.rotation_k ?? 'N/A'})</td></tr>
    </table>` : ''}

    <p class="section-title">Pipeline</p>
    <table class="kv-table">
      <tr><td>Residual filter</td><td>${det.filter}</td></tr>
      <tr><td>Scale-aware</td>   <td>${det.scale_aware ? badge('Yes','warning') : badge('No','neutral')}</td></tr>
      <tr><td>Image size</td>    <td>${d.image_size}</td></tr>
      <tr><td>Latency</td>       <td>${det.latency_ms} ms</td></tr>
    </table>

    ${det.scale_aware ? `<div class="report-box" style="margin-top:.75rem;font-size:.82rem;color:var(--warning)">
      ⚠ Scale-aware mode: BP được resize về kích thước ảnh trước NCC.<br>
      ρ không trực tiếp so sánh được với β = ${det.beta} của paper (benchmark 12MP).
    </div>` : ''}
  `;
}

// ── Tab: Localization ──────────────────────────────────────
function renderTabLocalization(d) {
  const loc = d.localization;
  const panel = $('tab-localization');

  if (!loc || !loc.available) {
    const reason = d.detection.detected === false
      ? 'Localization chỉ chạy khi BP được phát hiện.'
      : loc && loc.error ? `Lỗi: ${loc.error}` : 'Không có dữ liệu localization.';
    panel.innerHTML = `<div class="loc-na">${reason}</div>`;
    return;
  }

  const bokehPct = (loc.bokeh_ratio * 100).toFixed(1);
  panel.innerHTML = `
    <p class="section-title">NCC Localization Map</p>
    <div class="loc-grid">
      <div class="loc-item">
        <img class="loc-img" src="${loc.ncc_map_url}" alt="NCC Map"
             onclick="window.open('${loc.ncc_map_url}','_blank')" />
        <div class="loc-label">NCC Heatmap (JET)</div>
      </div>
      <div class="loc-item">
        <img class="loc-img" src="${loc.mask_url}" alt="Binary Mask"
             onclick="window.open('${loc.mask_url}','_blank')" />
        <div class="loc-label">Binary Mask (α = 0.07)</div>
      </div>
      <div class="loc-item">
        <img class="loc-img" src="${loc.overlay_url}" alt="Overlay"
             onclick="window.open('${loc.overlay_url}','_blank')" />
        <div class="loc-label">Overlay (ảnh gốc + NCC)</div>
      </div>
    </div>
    <p class="section-title">Thống kê</p>
    <table class="kv-table">
      <tr><td>Bokeh coverage</td><td><strong>${bokehPct}%</strong> diện tích ảnh</td></tr>
      <tr><td>NCC threshold (α)</td><td>0.07</td></tr>
      <tr><td>Block size</td><td>21 × 21 px</td></tr>
    </table>
    <p style="font-size:.75rem;color:var(--text-faint);margin-top:.6rem">
      Nhấn vào ảnh để xem full-size.
    </p>
  `;
}

// ── Tab: Report ────────────────────────────────────────────
function renderTabReport(d) {
  const sha = d.sha256;
  const ts  = d.timestamp.replace('T', ' ').slice(0, 19) + ' UTC';

  $('tab-report').innerHTML = `
    <p class="section-title">Kết luận Forensic</p>
    <div class="report-box">${escHtml(d.conclusion)}</div>

    <p class="section-title">Chain of Custody</p>
    <table class="kv-table">
      <tr><td>File</td>      <td>${escHtml(d.filename)}</td></tr>
      <tr><td>Size</td>      <td>${formatBytes(d.size_bytes)}</td></tr>
      <tr><td>Image size</td><td>${d.image_size}</td></tr>
      <tr><td>Timestamp</td> <td>${ts}</td></tr>
      <tr><td>Session ID</td><td><code>${d.session_id}</code></td></tr>
    </table>

    <p class="section-title">SHA-256 Hash</p>
    <div class="hash-box" title="Nhấn để copy" onclick="copyHash('${sha}')">${sha}</div>
    <p class="copy-hint">Nhấn vào hash để copy vào clipboard</p>

    <p class="section-title">Lưu ý</p>
    <div class="report-box" style="font-size:.8rem;color:var(--text-muted)">
      Kết quả này được tạo tự động bởi SDNP Forensic Analyzer (NT334.Q21.ANTT).<br>
      Kết luận sử dụng ngôn ngữ xác suất/hỗ trợ, không định danh tuyệt đối thiết bị nguồn.<br>
      Threshold β = ${d.detection.beta} theo paper: Vázquez-Padín et al., IEEE TIFS 2026.
    </div>
  `;
}

// ── Tabs ───────────────────────────────────────────────────
function initTabs() {
  document.addEventListener('click', e => {
    if (e.target.matches('.tab-btn')) {
      switchTab(e.target.dataset.tab);
    }
  });
}

function switchTab(tabId) {
  $$('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
  $$('.tab-pane').forEach(p => p.classList.toggle('active', p.id === `tab-${tabId}`));
}

// ── Results actions ────────────────────────────────────────
function initResultsActions() {
  document.addEventListener('click', e => {
    if (e.target.id === 'btn-new') resetToUpload();
  });
}

function resetToUpload() {
  clearFile();
  showSection('sec-upload');
  // Reset processing steps
  ['ps-upload','ps-hash','ps-exif','ps-bp','ps-loc','ps-rep'].forEach(id => {
    const el = $(id);
    if (el) { el.classList.remove('active','done'); }
  });
}

// ── Utilities ──────────────────────────────────────────────
function showSection(id) {
  $$('.sec').forEach(s => s.classList.remove('active'));
  const target = $(id);
  if (target) target.classList.add('active');
}

function formatBytes(b) {
  if (!b) return '—';
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b/1024).toFixed(1)} KB`;
  return `${(b/1048576).toFixed(2)} MB`;
}

function badge(text, type) {
  return `<span class="badge badge-${type}">${escHtml(String(text))}</span>`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

function copyHash(hash) {
  navigator.clipboard.writeText(hash).then(() => {
    showToast('SHA-256 đã được copy vào clipboard', 'ok');
  }).catch(() => {
    showToast('Không thể copy — hãy copy thủ công.');
  });
}

function showToast(msg, type = 'error') {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const el = document.createElement('div');
  el.className = 'toast';
  if (type === 'ok') el.style.background = 'var(--success)';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
