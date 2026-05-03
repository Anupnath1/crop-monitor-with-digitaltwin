const Dashboard = (() => {
  const API_BASE = window.API_BASE || 'http://localhost:5000';
  let realtimeChart = null;
  const MAX_POINTS = 20;
  const buffer = { labels: [], soil: [], temp: [], humidity: [], light: [] };
  let toastTimer = null;

  function showToast(msg, type = 'info') {
    const el = document.getElementById('toast');
    if (!el) return;
    clearTimeout(toastTimer);
    el.textContent = msg;
    el.className = `toast show ${type}`;
    toastTimer = setTimeout(() => { el.className = 'toast'; }, 3200);
  }

  function _startClock() {
    const el = document.getElementById('header-clock');
    if (!el) return;
    setInterval(() => {
      el.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }, 1000);
  }

  function _renderSensors(data) {
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const renderCard = (valId, barId, value, max) => {
      const valEl = document.getElementById(valId);
      const barEl = document.getElementById(barId);
      if (valEl) valEl.textContent = typeof value === 'number' ? value.toFixed(1) : '—';
      if (barEl) barEl.style.width = `${Math.min(100, Math.max(0, (value / max) * 100))}%`;
    };
    renderCard('val-soil',     'bar-soil',     data.soil,     100);
    renderCard('val-temp',     'bar-temp',     data.temp,     60);
    renderCard('val-humidity', 'bar-humidity', data.humidity, 100);
    renderCard('val-light',    'bar-light',    data.light,    1000);
    const lastEl = document.getElementById('last-update-time');
    if (lastEl) lastEl.textContent = now;
    buffer.labels.push(now);
    buffer.soil.push(data.soil);
    buffer.temp.push(data.temp);
    buffer.humidity.push(data.humidity);
    buffer.light.push(data.light);
    if (buffer.labels.length > MAX_POINTS) {
      ['labels','soil','temp','humidity','light'].forEach(k => buffer[k].shift());
    }
    _updateRealtimeChart();
  }

  function _renderHealth(score, explanation) {
    const ringEl  = document.getElementById('ring-fg');
    const scoreEl = document.getElementById('ring-score');
    const labelEl = document.getElementById('health-label');
    const explEl  = document.getElementById('health-explain');
    const offset  = 263.9 * (1 - score / 100);
    if (ringEl) {
      ringEl.style.strokeDashoffset = offset;
      ringEl.style.stroke = score >= 75 ? 'var(--ok)' : score >= 50 ? 'var(--warn)' : 'var(--crit)';
    }
    if (scoreEl) scoreEl.textContent = score.toFixed(0);
    if (labelEl) labelEl.textContent = score >= 75 ? 'Healthy' : score >= 50 ? 'Moderate' : 'Critical';
    if (explEl && explanation) explEl.textContent = explanation;
    if (typeof ThreeScene !== 'undefined') ThreeScene.updateHealth(score);
  }

  function _initRealtimeChart() {
    const ctx = document.getElementById('chart-realtime');
    if (!ctx) return;
    realtimeChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: buffer.labels,
        datasets: [
          { label: 'Soil %',    data: buffer.soil,     borderColor: '#5a84a0', borderWidth: 1.5, pointRadius: 1.5, tension: 0.5, fill: false },
          { label: 'Temp °C',   data: buffer.temp,     borderColor: '#b89a4e', borderWidth: 1.5, pointRadius: 1.5, tension: 0.5, fill: false },
          { label: 'Humidity %',data: buffer.humidity, borderColor: '#7a9e7e', borderWidth: 1.5, pointRadius: 1.5, tension: 0.5, fill: false },
        ]
      },
      options: _chartOpts(),
    });
  }

  function _updateRealtimeChart() {
    if (!realtimeChart) return;
    realtimeChart.data.labels = [...buffer.labels];
    realtimeChart.data.datasets[0].data = [...buffer.soil];
    realtimeChart.data.datasets[1].data = [...buffer.temp];
    realtimeChart.data.datasets[2].data = [...buffer.humidity];
    realtimeChart.update('none');
  }

  function _chartOpts() {
    return {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: {
        legend: { labels: { color: '#7a6e62', font: { family: 'DM Mono', size: 9 }, boxWidth: 12 } },
        tooltip: { backgroundColor: '#141210', borderColor: '#2a2520', borderWidth: 1, titleColor: '#c8bfb0', bodyColor: '#7a6e62', titleFont: { family: 'DM Mono', size: 10 } },
      },
      scales: {
        x: { ticks: { color: '#3d3830', font: { family: 'DM Mono', size: 8 }, maxTicksLimit: 6 }, grid: { color: '#1a1714' } },
        y: { ticks: { color: '#3d3830', font: { family: 'DM Mono', size: 8 } }, grid: { color: '#1a1714' } },
      },
    };
  }

  function _clampScore(v, lo, hi) {
    if (v >= lo && v <= hi) return 100;
    const dev = v < lo ? lo - v : v - hi;
    const worst = v < lo ? lo : (100 - hi);
    return Math.max(0, 100 - (dev / (worst || 1)) * 100);
  }

  document.addEventListener('sensorUpdate', async (e) => {
    const data = e.detail;
    _renderSensors(data);
    try {
      const res = await fetch(`${API_BASE}/get_health`, { signal: AbortSignal.timeout(3000) });
      if (res.ok) {
        const result = await res.json();
        if (result.success) { _renderHealth(result.health_score, result.explanation); return; }
      }
    } catch (_) {}
    const score = Math.min(100, Math.max(0,
      0.4 * _clampScore(data.soil || 50, 50, 80) +
      0.25 * _clampScore(data.temp || 25, 18, 30) +
      0.2  * _clampScore(data.humidity || 60, 50, 80) +
      0.15 * _clampScore(data.light || 400, 300, 700)
    ));
    _renderHealth(score, null);
  });

  async function simulateSensor() {
    const btn = document.getElementById('btn-simulate-sensor');
    btn.disabled = true;
    try {
      const res = await fetch(`${API_BASE}/simulate_sensor`, { method: 'POST' });
      const data = await res.json();
      if (data.success) showToast('Simulated sensor reading pushed to Firebase', 'success');
    } catch (err) {
      showToast('Sensor simulation failed: ' + err.message, 'error');
    } finally { btn.disabled = false; }
  }

  async function trainModel() {
    const btn = document.getElementById('btn-train');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Training…';
    try {
      const res  = await fetch(`${API_BASE}/train_model`, { method: 'POST' });
      const data = await res.json();
      if (data.success) showToast(`Model trained ✓ — ${data.metrics.n_samples} samples`, 'success');
      else showToast(`Training failed: ${data.error}`, 'error');
    } catch (err) {
      showToast('Training error: ' + err.message, 'error');
    } finally { btn.disabled = false; btn.innerHTML = '🧠 Train Model'; }
  }

  function init() {
    _startClock();
    _initRealtimeChart();
    document.getElementById('btn-simulate-sensor').addEventListener('click', simulateSensor);
    document.getElementById('btn-train').addEventListener('click', trainModel);
    showToast('AgroTwin dashboard loaded', 'info');
  }

  return { init, showToast };
})();

document.addEventListener('DOMContentLoaded', () => { Dashboard.init(); });
