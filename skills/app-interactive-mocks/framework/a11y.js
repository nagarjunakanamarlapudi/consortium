/* a11y.js — accessibility audit for app-interactive-mocks.
   Pure colour math (hexToRgb/relLuminance/contrastRatio/wcagLevel) is node-testable.
   DOM helpers build the audit section and recompute on themechange. */
(function (global) {
  function hexToRgb(hex) {
    let h = String(hex).replace('#', '').trim();
    if (h.length === 3) h = h.split('').map(c => c + c).join('');
    const n = parseInt(h, 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }
  function relLuminance(hex) {
    const { r, g, b } = hexToRgb(hex);
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  }
  function contrastRatio(a, b) {
    const L1 = relLuminance(a), L2 = relLuminance(b);
    const hi = Math.max(L1, L2), lo = Math.min(L1, L2);
    return (hi + 0.05) / (lo + 0.05);
  }
  function wcagLevel(ratio, opts) {
    const large = opts && opts.large;
    if (!large && ratio >= 7) return 'AAA';
    if (large && ratio >= 4.5) return 'AAA';
    if (!large && ratio >= 4.5) return 'AA';
    if (large && ratio >= 3) return 'AA';
    return 'fail';
  }
  // --- DOM (browser only) ---
  function token(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function auditTapTargets(rootEl, opts) {
    const min = (opts && opts.min) || 44;
    const sel = 'button, a, [onclick], [onpointerdown], .tab, input, select';
    return Array.prototype.slice.call(rootEl.querySelectorAll(sel)).map(el => {
      const r = el.getBoundingClientRect();
      return { label: (el.getAttribute('aria-label') || el.textContent || el.tagName).trim().slice(0, 40),
               w: Math.round(r.width), h: Math.round(r.height), pass: r.width >= min && r.height >= min };
    });
  }
  function row(label, ratio, large) {
    const lvl = wcagLevel(ratio, { large });
    return `<tr><td>${label}</td><td>${ratio.toFixed(2)}:1</td><td class="${lvl === 'fail' ? 'fail' : 'pass'}">${lvl}</td></tr>`;
  }
  function mountAudit(hostElId) {
    const host = document.getElementById(hostElId);
    if (!host) return;
    function paint() {
      const bg = token('--card') || token('--bg') || '#ffffff';
      const pairs = [
        ['Body text on card', token('--text'), bg, false],
        ['Muted text on card', token('--muted'), bg, false],
        ['Primary on card', token('--primary'), bg, true],
      ].filter(p => p[1] && p[2]);
      const contrastRows = pairs.map(p => row(p[0], contrastRatio(p[1], p[2]), p[3])).join('');
      const screen = document.getElementById('screen');
      const taps = screen ? auditTapTargets(screen, { min: 44 }) : [];
      const tapRows = taps.map(t => `<tr><td>${t.label}</td><td>${t.w}×${t.h}</td><td class="${t.pass ? 'pass' : 'fail'}">${t.pass ? 'pass' : '&lt; 44pt'}</td></tr>`).join('')
        || '<tr><td colspan="3">Render the playground to audit tap targets.</td></tr>';
      host.innerHTML = `
        <h3>Contrast (active theme)</h3>
        <table><thead><tr><th>Pair</th><th>Ratio</th><th>WCAG 2.2</th></tr></thead><tbody>${contrastRows}</tbody></table>
        <h3>Tap targets</h3>
        <table><thead><tr><th>Element</th><th>Size</th><th>≥ 44pt</th></tr></thead><tbody>${tapRows}</tbody></table>
        <h3>Semantics &amp; focus order</h3>
        <p class="lead">TODO (author): role · accessible label · hint · state per interactive element; declared focus/traversal order. Confirm reduced-motion fallback for transitions.</p>`;
    }
    paint();
    global.addEventListener('themechange', paint);
    global.addEventListener('screenchange', paint);
  }
  const A11y = { hexToRgb, relLuminance, contrastRatio, wcagLevel, auditTapTargets, mountAudit };
  global.A11y = A11y;
  if (typeof module !== 'undefined' && module.exports) module.exports = A11y;
})(typeof window !== 'undefined' ? window : globalThis);
