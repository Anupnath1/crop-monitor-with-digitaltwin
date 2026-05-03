const FirebaseListener = (() => {
  let db = null;

  function init() {
    try {
      if (!firebase.apps || firebase.apps.length === 0) {
        firebase.initializeApp(window.firebaseConfig);
      }
      db = firebase.database();
      _attachListeners();
      _setStatus('connected');
    } catch (err) {
      console.error('[Firebase] Init failed:', err.message);
      _setStatus('error', err.message);
    }
  }

  function _attachListeners() {
    db.ref('farm/current').on('value', (snap) => {
      if (!snap.exists()) return;
      const raw = snap.val();
      // Remap field names to what your dashboard expects
      const latest = {
        soil:     raw.soil_moisture,
        temp:     raw.temperature,
        humidity: raw.humidity,
        light:    raw.light_intensity,
        timestamp: raw.timestamp,
      };
      document.dispatchEvent(new CustomEvent('sensorUpdate', { detail: latest }));
    });

    db.ref('irrigation').on('value', (snap) => {
      if (!snap.exists()) return;
      document.dispatchEvent(new CustomEvent('irrigationUpdate', { detail: snap.val() }));
    });

    db.ref('predictions').orderByKey().limitToLast(1).on('value', (snap) => {
      if (!snap.exists()) return;
      const latest = Object.values(snap.val())[0];
      document.dispatchEvent(new CustomEvent('predictionUpdate', { detail: latest }));
    });
  }

  function _setStatus(state, detail) {
    const dot  = document.getElementById('firebase-status-dot');
    const text = document.getElementById('firebase-status-text');
    if (!dot || !text) return;
    const map = {
      connected: { cls: 'connected', label: 'Firebase live' },
      error:     { cls: 'error',     label: 'Firebase error — check config' },
    };
    const s = map[state] || { cls: '', label: state };
    dot.className    = `status-dot ${s.cls}`;
    text.textContent = s.label;
    if (state === 'error' && detail) console.error('[Firebase]', detail);
  }

  return { init };
})();

document.addEventListener('DOMContentLoaded', () => { FirebaseListener.init(); });
