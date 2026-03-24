/* ============================================================
   ALPR RPi4 — Dashboard Frontend
   Polls /api/status and /api/history on a configurable interval.
   Renders stats, history table, rate chart, and unique plates.
   ============================================================ */

'use strict';

// ── State ─────────────────────────────────────────────────────
let _pollInterval = 2000;
let _timer        = null;
let _online       = false;

// Rate chart: ring buffer of detection counts per poll
const CHART_BUCKETS  = 20;
const _rateBuckets   = new Array(CHART_BUCKETS).fill(0);
let   _prevTotal     = 0;

// ── DOM refs ──────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const elFps       = $('stat-fps');
const elTotal     = $('stat-total');
const elUptime    = $('stat-uptime');
const elLastPlate = $('stat-last-plate');
const elBadge     = $('connection-badge');
const elBadgeLbl  = $('connection-label');
const elHistBody  = $('history-body');
const elUnique    = $('unique-plates');
const elUniqueCnt = $('unique-count');
const elChart     = $('rate-chart');
const elStreamImg = $('stream-img');
const elStreamOvl = $('stream-overlay');
const elIntLabel  = $('interval-label');
const ctx         = elChart.getContext('2d');

// ── Helpers ───────────────────────────────────────────────────
function fmtUptime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

function setOnline(online) {
  if (_online === online) return;
  _online = online;
  elBadge.className = 'status-pill ' + (online ? 'online' : 'offline');
  elBadgeLbl.textContent = online ? 'Online' : 'Offline';
}

// ── Polling ───────────────────────────────────────────────────
async function poll() {
  try {
    const [statusRes, histRes] = await Promise.all([
      fetch('/api/status'),
      fetch('/api/history'),
    ]);

    if (!statusRes.ok || !histRes.ok) throw new Error('bad response');

    const status  = await statusRes.json();
    const history = await histRes.json();

    setOnline(true);
    renderStatus(status);
    renderHistory(history);
    updateRateChart(status.total_detections);
    renderUniquePlates(history);

  } catch {
    setOnline(false);
  }
}

// ── Render: status ────────────────────────────────────────────
function renderStatus(s) {
  elFps.textContent       = s.fps ?? '—';
  elTotal.textContent     = s.total_detections ?? '—';
  elUptime.textContent    = s.uptime_seconds != null ? fmtUptime(s.uptime_seconds) : '—';
  elLastPlate.textContent = s.last_plate || '—';
}

// ── Render: history table ─────────────────────────────────────
function renderHistory(history) {
  // Show newest first, cap at 15 rows
  const rows = [...history].reverse().slice(0, 15);

  if (rows.length === 0) {
    elHistBody.innerHTML = '<tr class="empty-row"><td colspan="5">No detections yet</td></tr>';
    return;
  }

  elHistBody.innerHTML = rows.map(r => {
    const colorCls = `color-${(r.color || 'unknown').toLowerCase()}`;
    const detPct   = Math.round((r.det_conf || 0) * 100);
    const ocrPct   = Math.round((r.ocr_conf || 0) * 100);
    return `<tr>
      <td><span class="plate-badge">${esc(r.plate)}</span></td>
      <td class="${colorCls}">${esc(r.color || '—')}</td>
      <td>${detPct}%</td>
      <td>${ocrPct}%</td>
      <td>${esc(r.time_str || '—')}</td>
    </tr>`;
  }).join('');
}

// ── Render: unique plates ─────────────────────────────────────
function renderUniquePlates(history) {
  const seen  = new Map(); // plate → latest det_conf
  for (const r of history) {
    if (r.plate) seen.set(r.plate, r.det_conf);
  }
  elUniqueCnt.textContent = seen.size;

  if (seen.size === 0) {
    elUnique.innerHTML = '<span style="color:var(--text-dim);font-size:0.8rem;">No data yet</span>';
    return;
  }

  elUnique.innerHTML = [...seen.keys()].sort().map(p =>
    `<div class="plate-chip">${esc(p)}</div>`
  ).join('');
}

// ── Chart ─────────────────────────────────────────────────────
function updateRateChart(currentTotal) {
  const delta = Math.max(0, currentTotal - _prevTotal);
  _prevTotal  = currentTotal;

  _rateBuckets.shift();
  _rateBuckets.push(delta);

  drawChart();
}

function drawChart() {
  const W    = elChart.offsetWidth  || 400;
  const H    = 120;
  elChart.width  = W;
  elChart.height = H;

  const pad    = { top: 12, right: 10, bottom: 20, left: 34 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top  - pad.bottom;

  ctx.clearRect(0, 0, W, H);

  const max = Math.max(..._rateBuckets, 1);
  const barW = innerW / CHART_BUCKETS;

  // Grid lines
  ctx.strokeStyle = '#1e2240';
  ctx.lineWidth   = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.top + innerH - (innerH * i / 4);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(pad.left + innerW, y);
    ctx.stroke();
  }

  // Bars
  _rateBuckets.forEach((v, i) => {
    const barH = (v / max) * innerH;
    const x    = pad.left + i * barW + 2;
    const y    = pad.top + innerH - barH;
    const alpha = 0.4 + 0.6 * (i / (CHART_BUCKETS - 1));

    ctx.fillStyle = `rgba(0, 212, 255, ${alpha})`;
    ctx.fillRect(x, y, barW - 4, barH);
  });

  // Y axis labels
  ctx.fillStyle  = '#7a7a9a';
  ctx.font       = '10px monospace';
  ctx.textAlign  = 'right';
  for (let i = 0; i <= 2; i++) {
    const val = Math.round(max * i / 2);
    const y   = pad.top + innerH - (innerH * i / 2) + 3;
    ctx.fillText(val, pad.left - 4, y);
  }

  // X label
  ctx.textAlign  = 'center';
  ctx.fillStyle  = '#7a7a9a';
  ctx.fillText('detections / poll', pad.left + innerW / 2, H - 4);
}

// ── Stream error handling ─────────────────────────────────────
window.handleStreamError = function() {
  elStreamImg.style.display = 'none';
  elStreamOvl.classList.remove('hidden');
};

// Reconnect stream after offline → online
let _streamRetryTimer = null;
function retryStream() {
  clearInterval(_streamRetryTimer);
  _streamRetryTimer = setInterval(() => {
    if (_online) {
      elStreamImg.src = '/stream?' + Date.now();
      elStreamImg.style.display = '';
      elStreamOvl.classList.add('hidden');
      clearInterval(_streamRetryTimer);
    }
  }, 3000);
}
elStreamImg.addEventListener('error', () => {
  handleStreamError();
  retryStream();
});

// ── Clear history ─────────────────────────────────────────────
window.clearHistory = async function() {
  try {
    await fetch('/api/clear', { method: 'POST' });
    _prevTotal = 0;
    _rateBuckets.fill(0);
    await poll();
  } catch {
    // ignore
  }
};

// ── Interval control ──────────────────────────────────────────
window.setInterval_ = function(ms) {
  _pollInterval = parseInt(ms, 10);
  elIntLabel.textContent = ms >= 1000 ? `${ms / 1000}s` : `${ms}ms`;
  restartTimer();
};

function restartTimer() {
  if (_timer) clearInterval(_timer);
  _timer = setInterval(poll, _pollInterval);
}

// ── XSS-safe escape ───────────────────────────────────────────
function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Init ──────────────────────────────────────────────────────
window.addEventListener('resize', drawChart);
drawChart();  // draw empty chart immediately
poll();       // first poll right away
restartTimer();
