/**
 * app.js — shared utilities for all pages
 * Include AFTER style.css, BEFORE page-specific scripts
 */
const AgroApp = (() => {
  const API_BASE = window.API_BASE || 'http://localhost:5000';
  let _toastTimer = null;

  function toast(msg, type = 'info') {
    let el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = `toast show ${type}`;
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => { el.className = 'toast'; }, 3500);
  }

  function initClock() {
    const update = () => {
      const t = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      document.querySelectorAll('#header-clock').forEach(el => { el.textContent = t; });
    };
    update();
    setInterval(update, 1000);
  }

  function initOfflineBanner() {
    const banner = document.getElementById('offline-banner');
    if (!banner) return;
    // Set text content
    banner.textContent = '⚠ No internet connection — some features may be unavailable';
    const update = () => banner.classList.toggle('show', !navigator.onLine);
    window.addEventListener('online',  update);
    window.addEventListener('offline', update);
    update();
  }

  function healthColor(score) {
    return score >= 75 ? 'var(--ok)' : score >= 50 ? 'var(--warn)' : 'var(--crit)';
  }
  function healthBg(score) {
    return score >= 75 ? 'var(--sage-dim)' : score >= 50 ? 'var(--warn)' : 'var(--crit)';
  }
  function healthLabel(score) {
    return score >= 75 ? 'Healthy' : score >= 50 ? 'Moderate' : 'Critical';
  }

  document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initOfflineBanner();
  });

  return { API_BASE, toast, healthColor, healthBg, healthLabel };
})();
