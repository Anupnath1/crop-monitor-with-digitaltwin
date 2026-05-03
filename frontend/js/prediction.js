const Prediction = (() => {
  const API_BASE = window.API_BASE || 'http://localhost:5000';
  let selectedHours = 1;
  let predictionChart = null;

  function init() {
    document.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        const hours = chip.dataset.hours;
        const customInput = document.getElementById('custom-hours');
        if (hours === 'custom') {
          customInput.classList.remove('hidden');
          selectedHours = parseFloat(customInput.value) || 1;
        } else {
          customInput.classList.add('hidden');
          selectedHours = parseFloat(hours);
        }
      });
    });

    document.getElementById('custom-hours').addEventListener('input', e => {
      const v = parseFloat(e.target.value);
      if (!isNaN(v) && v > 0) selectedHours = v;
    });

    document.getElementById('btn-predict').addEventListener('click', runPrediction);

    const ctx = document.getElementById('chart-prediction');
    if (ctx) {
      predictionChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            { label: 'Soil %',    data: [], borderColor: '#5a84a0', borderWidth: 1.5, pointRadius: 2, tension: 0.4, fill: false },
            { label: 'Temp °C',   data: [], borderColor: '#b89a4e', borderWidth: 1.5, pointRadius: 2, tension: 0.4, fill: false },
            { label: 'Humidity %',data: [], borderColor: '#7a9e7e', borderWidth: 1.5, pointRadius: 2, tension: 0.4, fill: false },
          ]
        },
        options: {
          responsive: true, maintainAspectRatio: false, animation: { duration: 400 },
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { labels: { color: '#7a6e62', font: { family: 'DM Mono', size: 9 }, boxWidth: 12 } },
            tooltip: { backgroundColor: '#141210', borderColor: '#2a2520', borderWidth: 1, titleColor: '#c8bfb0', bodyColor: '#7a6e62', titleFont: { family: 'DM Mono', size: 10 } },
          },
          scales: {
            x: { ticks: { color: '#3d3830', font: { family: 'DM Mono', size: 8 } }, grid: { color: '#1a1714' } },
            y: { ticks: { color: '#3d3830', font: { family: 'DM Mono', size: 8 } }, grid: { color: '#1a1714' } },
          },
        },
      });
    }
  }

  async function runPrediction() {
    const btn = document.getElementById('btn-predict');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Predicting…';
    try {
      const predRes = await fetch(`${window.API_BASE || 'http://localhost:5000'}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hours: selectedHours }),
      });
      const predData = await predRes.json();
      if (!predData.success) throw new Error(predData.error || 'Prediction failed');

      const { predictions } = predData;
      _renderPredictions(predictions);

      const recRes = await fetch(`${window.API_BASE || 'http://localhost:5000'}/get_recommendation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hours: selectedHours }),
      });
      const recData = await recRes.json();
      if (recData.success) {
        if (typeof Irrigation !== 'undefined') {
          Irrigation.renderRecommendation(recData.recommendation);
          Irrigation.renderIrrigationInfo(recData.irrigation);
        }
      }

      if (typeof ThreeScene !== 'undefined') ThreeScene.updateHealth(predictions.health_score);
      _updatePredictionChart(predictions);

      if (typeof Dashboard !== 'undefined') Dashboard.showToast(`Prediction for +${selectedHours}h complete`, 'success');
    } catch (err) {
      if (typeof Dashboard !== 'undefined') Dashboard.showToast(`Prediction error: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '▶ Run Prediction';
    }
  }

  function _renderPredictions(predictions) {
    const set = (id, val, dp = 1) => {
      const el = document.getElementById(id);
      if (el) {
        el.textContent = typeof val === 'number' ? val.toFixed(dp) : '—';
        el.style.color = 'var(--ok)';
        setTimeout(() => { el.style.color = ''; }, 600);
      }
    };
    set('pred-soil',     predictions.soil,         1);
    set('pred-temp',     predictions.temp,          1);
    set('pred-humidity', predictions.humidity,      1);
    set('pred-light',    predictions.light,         0);
    set('pred-health',   predictions.health_score,  1);

    const healthEl = document.getElementById('pred-health');
    if (healthEl) {
      const s = predictions.health_score;
      healthEl.style.color = s >= 75 ? 'var(--ok)' : s >= 50 ? 'var(--warn)' : 'var(--crit)';
    }
    const explEl = document.getElementById('pred-explain');
    if (explEl && predictions.explanation) explEl.textContent = predictions.explanation;
  }

  function _updatePredictionChart(predictions) {
    if (!predictionChart) return;
    predictionChart.data.labels.push(`+${selectedHours}h`);
    predictionChart.data.datasets[0].data.push(predictions.soil);
    predictionChart.data.datasets[1].data.push(predictions.temp);
    predictionChart.data.datasets[2].data.push(predictions.humidity);
    if (predictionChart.data.labels.length > 12) {
      predictionChart.data.labels.shift();
      predictionChart.data.datasets.forEach(d => d.data.shift());
    }
    predictionChart.update('active');
  }

  return { init, runPrediction };
})();

document.addEventListener('DOMContentLoaded', () => { Prediction.init(); });
