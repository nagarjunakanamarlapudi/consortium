/* ==========================================================================
   state-swap.js — Catalog tile renderer using state-swap pattern
   ==========================================================================
   The catalog section shows the SAME render path as the playground but with
   per-tile state mutations. This guarantees catalog tiles can never visually
   drift from the playground — they share the same render function.
   Supports optional per-screen catalog tiles via `data-screen` on .phone-frame.

   Usage in your feature HTML:
     1. Define a catalogScreen(stateName) function that calls withTempState()
     2. Call mountCatalog() at script-end to render every .phone-frame[data-state]

   Example:
     function catalogScreen(name) {
       return withTempState(temp => {
         switch (name) {
           case 'default': break;
           case 'loading': temp.loading = true; break;
           case 'empty':   temp.deleted = temp.items.map(i => i.id); break;
         }
       }, () => render());          // your feature's render fn
     }
     mountCatalog(catalogScreen);
   ========================================================================== */

/**
 * Run `mutate(temp)` on a deep clone of the global `state`, then call
 * `renderFn()` to get HTML. Restores `state` afterwards.
 *
 * The page must define globally:
 *   - state         the live state object
 *   - render fn     a function that reads state and returns HTML
 */
function withTempState(mutate, renderFn) {
  if (typeof state === 'undefined') {
    console.error('[state-swap] global `state` is undefined');
    return '';
  }
  const orig = state;
  // eslint-disable-next-line no-global-assign
  state = JSON.parse(JSON.stringify(state));
  try {
    if (typeof mutate === 'function') mutate(state);
    return renderFn();
  } finally {
    // restore
    // eslint-disable-next-line no-global-assign
    state = orig;
  }
}

/**
 * Iterate every `.phone-frame[data-state]` in the document, call
 * `catalogFn(stateName[, screenId])` for each, and inject the resulting HTML into the
 * frame's `.phone-screen`. If the frame has a `data-screen` attribute and catalogFn
 * declares 2 parameters, the screenId is passed as the second argument.
 */
function mountCatalog(catalogFn) {
  document.querySelectorAll('.phone-frame[data-state]').forEach(frame => {
    const stateName = frame.dataset.state;
    const screenId = frame.dataset.screen; // optional — for multi-screen flows
    const screen = frame.querySelector('.phone-screen');
    if (!screen) return;
    screen.innerHTML = (catalogFn.length >= 2) ? catalogFn(stateName, screenId) : catalogFn(stateName);
  });
}

/**
 * For theme pair (.phone-screen#theme-light, #theme-dark) — usually rendered
 * with the default state but the dark one in dark mode (handled via .dark class).
 */
function mountThemePair(catalogFn) {
  const light = document.getElementById('theme-light');
  const dark = document.getElementById('theme-dark');
  if (light) light.innerHTML = catalogFn('default');
  if (dark) dark.innerHTML = catalogFn('default');
}

/* ----- HTML escape helper for embedding user-supplied strings in onclick attrs ----- */
function jsAttr(v) {
  return JSON.stringify(v).replace(/"/g, '&quot;');
}
