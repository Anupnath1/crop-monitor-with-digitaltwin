const Prediction = (() => {
  const API_BASE = window.API_BASE || 'http://localhost:5000';
  let selectedHours = 1;
  let soilForecastChart = null;
  let allHorizonsChart  = null;

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

    // Chart 1: soil forecast over time (accumulates across runs)
    const ctx1 = document.getElementById('chart-prediction');
    if (ctx1) {
      soilForecastChart = new Chart(ctx1, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Predicted Soil %',
              data: [],
              borderColor: '#5a84a0',
              borderWidth: 2,
              pointRadius: 4,
              pointBackgroundColor: '#5a84a0',
              tension: 0.4,
              fill: true,
              backgroundColor: 'rgba(90,132,160,0.08)',
            }
          ]
        },
        options: _chartOpts('Soil Moisture %'),
      });
    }

    // Chart 2: all horizons from latest prediction run
    const ctx2 = document.getElementById('chart-all-horizons');
    if (ctx2) {
      allHorizonsChart = new Chart(ctx2, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Soil % by horizon',
              data: [],
              borderColor: '#7a9e7e',
              borderWidth: 2,
              pointRadius: 3,
              pointBackgroundColor: '#7a9e7e',
              tension: 0.35,
              fill: true,
              backgroundColor: 'rgba(122,158,126,0.07)',
            }
          ]
        },
        options: _chartOpts('All Horizons — Soil %'),
      });
    }
  }

  async function runPrediction() {
    const btn = document.getElementById('btn-predict');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Predicting…';

    try {
      const predRes = await fetch(`${API_BASE}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hours: selectedHours }),
      });
      const predData = await predRes.json();
      if (!predData.success) throw new Error(predData.error || 'Prediction failed');

      const { predictions } = predData;

      _renderPredictions(predictions);
      _updateSoilForecastChart(predictions);
      _updateAllHorizonsChart(predictions.all_horizons);

      // fetch recommendation separately
      const recRes = await fetch(`${API_BASE}/get_recommendation`, {
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
      if (typeof Dashboard !== 'undefined') Dashboard.showToast(`Soil forecast for +${selectedHours}h complete`, 'success');

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
      if (!el) return;
      el.textContent = typeof val === 'number' ? val.toFixed(dp) : val;
      el.style.color = 'var(--ok)';
      setTimeout(() => { el.style.color = ''; }, 600);
    };

    // Soil is predicted
    set('pred-soil', predictions.soil, 1);

    // These are current readings, not predictions — label them accordingly
    set('pred-temp',     predictions.temp,     1);
    set('pred-humidity', predictions.humidity, 1);
    set('pred-light',    predictions.light,    0);

    // Health score and explanation
    set('pred-health', predictions.health_score, 1);
    const healthEl = document.getElementById('pred-health');
    if (healthEl) {
      const s = predictions.health_score;
      healthEl.style.color = s >= 75 ? 'var(--ok)' : s >= 50 ? 'var(--warn)' : 'var(--crit)';
    }

    const explEl = document.getElementById('pred-explain');
    if (explEl && predictions.explanation) explEl.textContent = predictions.explanation;

    // Mark non-soil fields as current readings, not forecasts
    ['pred-temp-note', 'pred-humidity-note', 'pred-light-note'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = '(current reading)';
    });
  }

  // Accumulates soil predictions across multiple runs
  function _updateSoilForecastChart(predictions) {
    if (!soilForecastChart) return;
    const label = `+${selectedHours}h`;
    soilForecastChart.data.labels.push(label);
    soilForecastChart.data.datasets[0].data.push(predictions.soil);
    if (soilForecastChart.data.labels.length > 12) {
      soilForecastChart.data.labels.shift();
      soilForecastChart.data.datasets[0].data.shift();
    }
    soilForecastChart.update('active');
  }

  // Shows all horizon predictions from the latest run (5min to 300min)
  function _updateAllHorizonsChart(allHorizons) {
    if (!allHorizonsChart || !allHorizons) return;

    // allHorizons is { "5": 62.3, "10": 61.8, ... }
    const entries = Object.entries(allHorizons)
      .map(([k, v]) => ({ min: parseInt(k), val: v }))
      .sort((a, b) => a.min - b.min);

    allHorizonsChart.data.labels   = entries.map(e => `${e.min}m`);
    allHorizonsChart.data.datasets[0].data = entries.map(e => e.val);
    allHorizonsChart.update('none');
  }

  function _chartOpts(title) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { labels: { color: '#7a6e62', font: { family: 'DM Mono', size: 9 }, boxWidth: 12 } },
        tooltip: {
          backgroundColor: '#ffffff', borderColor: '#e4dbd2', borderWidth: 1,
          titleColor: '#2f2a24', bodyColor: '#615a51',
          titleFont: { family: 'DM Mono', size: 10 },
        },
      },
      scales: {
        x: { ticks: { color: '#615a51', font: { family: 'DM Mono', size: 8 } }, grid: { color: '#e8e1d9' } },
        y: {
          ticks: { color: '#615a51', font: { family: 'DM Mono', size: 8 } },
          grid: { color: '#e8e1d9' },
          min: 0, max: 100,
          title: { display: true, text: '%', color: '#615a51', font: { family: 'DM Mono', size: 8 } }
        },
      },
    };
  }

  return { init, runPrediction };
})();

document.addEventListener('DOMContentLoaded', () => { Prediction.init(); });
