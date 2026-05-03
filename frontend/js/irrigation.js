const Irrigation = (() => {
  const API_BASE = window.API_BASE || 'http://localhost:5000';

  function init() {
    document.getElementById('btn-simulate-pump').addEventListener('click', simulatePump);
  }

  async function simulatePump() {
    const btn = document.getElementById('btn-simulate-pump');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Simulating…';
    const waterEl = document.getElementById('irr-water');
    const waterLiters = parseFloat((waterEl ? waterEl.textContent : '2')) || 2.0;
    try {
      const res = await fetch(`${API_BASE}/simulate_irrigation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ water_liters: waterLiters }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Simulation failed');
      _renderSimulation(data.simulation);
      if (typeof Dashboard !== 'undefined') Dashboard.showToast(`Pump simulated: +${data.simulation.water_added_liters}L applied`, 'success');
    } catch (err) {
      if (typeof Dashboard !== 'undefined') Dashboard.showToast(`Simulation error: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '💦 Simulate Pump Cycle';
    }
  }

  function _renderSimulation(sim) {
    const resultWrap = document.getElementById('moisture-sim-result');
    if (resultWrap) resultWrap.classList.remove('hidden');

    if (typeof ThreeScene !== 'undefined' && ThreeScene.triggerWater) {
      const vizSeconds = Math.min(12, sim.runtime_minutes * 60 * 0.05 + 4);
      ThreeScene.triggerWater(vizSeconds);
    }

    requestAnimationFrame(() => {
      const barBefore = document.getElementById('sim-bar-before');
      const barAfter  = document.getElementById('sim-bar-after');
      const afterVal  = document.getElementById('sim-after-val');
      if (barBefore) barBefore.style.width = `${Math.min(100, sim.initial_moisture)}%`;
      if (barAfter)  barAfter.style.width  = `${Math.min(100, sim.final_moisture)}%`;
      if (afterVal)  afterVal.textContent  = sim.final_moisture.toFixed(1);
    });

    const dot   = document.getElementById('pump-dot');
    const label = document.getElementById('pump-label');
    if (dot && label) {
      dot.className    = 'pump-dot on';
      label.textContent = `Pump: ON (${sim.runtime_minutes} min)`;
      setTimeout(() => {
        dot.className    = 'pump-dot off';
        label.textContent = 'Pump: OFF (cycle complete)';
      }, sim.runtime_minutes * 1000 + 2000);
    }
  }

  function renderRecommendation(rec) {
    const urgencyEl = document.getElementById('rec-urgency');
    const messageEl = document.getElementById('rec-message');
    const actionsEl = document.getElementById('rec-actions');
    if (urgencyEl) { urgencyEl.textContent = rec.urgency; urgencyEl.className = `rec-urgency ${rec.urgency}`; }
    if (messageEl) messageEl.textContent = rec.message;
    if (actionsEl) actionsEl.innerHTML = (rec.actions || []).map(a => `<li>${a}</li>`).join('');
  }

  function renderIrrigationInfo(irrigation) {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('irr-water',   `${irrigation.water_needed_liters} L`);
    set('irr-runtime', `${irrigation.runtime_minutes} min`);
    set('irr-deficit', `${irrigation.moisture_deficit}%`);
    const dot   = document.getElementById('pump-dot');
    const label = document.getElementById('pump-label');
    if (dot && label) {
      if (irrigation.irrigation_needed) {
        dot.className    = 'pump-dot needed';
        label.textContent = 'Pump: Required';
      } else {
        dot.className    = 'pump-dot off';
        label.textContent = 'Pump: Not required';
      }
    }
  }

  document.addEventListener('irrigationUpdate', e => {
    if (e.detail) renderIrrigationInfo(e.detail);
  });

  return { init, renderRecommendation, renderIrrigationInfo };
})();

document.addEventListener('DOMContentLoaded', () => { Irrigation.init(); });
