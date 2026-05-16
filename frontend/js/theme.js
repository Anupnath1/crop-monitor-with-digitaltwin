/**
 * theme.js
 * Reads CSS custom properties at runtime so chart colors always
 * match the current theme (light or dark) without hardcoding hex values.
 * Include this AFTER style.css and BEFORE any chart JS.
 */
const Theme = (() => {
  function get(varName) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(varName).trim();
  }

  function colors() {
    return {
      bg:       get('--bg'),
      surface:  get('--surface'),
      surface2: get('--surface2'),
      border:   get('--border'),
      border2:  get('--border2'),
      text:     get('--text'),
      text2:    get('--text-2'),
      text3:    get('--text-3'),
      sage:     get('--sage'),
      sageDim:  get('--sage-dim'),
      ok:       get('--ok'),
      warn:     get('--warn'),
      crit:     get('--crit'),
      blue:     get('--blue'),
    };
  }

  /**
   * Standard Chart.js options using live CSS variables.
   * Call this each time you create a chart — not once at module load —
   * so colors are always current.
   */
  function chartOpts(extra = {}) {
    const c = colors();
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: {
            color: c.text2,
            font: { family: 'DM Mono', size: 9 },
            boxWidth: 12,
          },
        },
        tooltip: {
          backgroundColor: c.surface,
          borderColor: c.border2,
          borderWidth: 1,
          titleColor: c.text,
          bodyColor: c.text2,
          titleFont: { family: 'DM Mono', size: 10 },
          bodyFont:  { family: 'DM Mono', size: 10 },
        },
      },
      scales: {
        x: {
          ticks: { color: c.text3, font: { family: 'DM Mono', size: 8 } },
          grid:  { color: c.border },
        },
        y: {
          ticks: { color: c.text3, font: { family: 'DM Mono', size: 8 } },
          grid:  { color: c.border },
          ...extra,
        },
      },
    };
  }

  return { get, colors, chartOpts };
})();
