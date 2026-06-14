/* theme-selector.js — theme gallery registry + live dropdown.
   Applies a theme by setting document.documentElement.dataset.theme.
   Pure: ThemeKit.THEMES (node-testable). */
(function (global) {
  const THEMES = [
    { id: 'neutral',     name: 'Neutral (default)' },
    { id: 'indigo',      name: 'Indigo' },
    { id: 'teal',        name: 'Teal' },
    { id: 'emerald',     name: 'Emerald' },
    { id: 'rose',        name: 'Rose' },
    { id: 'amber',       name: 'Amber' },
    { id: 'violet',      name: 'Violet' },
    { id: 'sky',         name: 'Sky' },
    { id: 'orange',      name: 'Orange' },
    { id: 'crimson',     name: 'Crimson' },
    { id: 'cyan',        name: 'Cyan' },
    { id: 'lime',        name: 'Lime' },
    { id: 'fuchsia',     name: 'Fuchsia' },
    { id: 'slate',       name: 'Slate (mono)' },
    { id: 'material-you', name: 'Material You' },
    { id: 'ios',         name: 'iOS System' },
    { id: 'nord',        name: 'Nord' },
    { id: 'dracula',     name: 'Dracula' },
    { id: 'solarized',   name: 'Solarized' },
    { id: 'catppuccin',  name: 'Catppuccin' },
    { id: 'tokyo-night', name: 'Tokyo Night' },
    { id: 'rose-pine',   name: 'Rosé Pine' },
    { id: 'gruvbox',     name: 'Gruvbox' },
    { id: 'one-dark',    name: 'One Dark' },
  ];
  function applyTheme(id) {
    document.documentElement.dataset.theme = id;
    global.dispatchEvent(new CustomEvent('themechange', { detail: { id } }));
  }
  function renderThemeSelector() {
    return `<span class="theme-select"><select id="theme-select" aria-label="Theme">${
      THEMES.map(t => `<option value="${t.id}">${t.name}</option>`).join('')
    }</select></span>`;
  }
  function mountThemeSelector(defaultId) {
    const id = defaultId || 'neutral';
    applyTheme(id);
    const sel = document.getElementById('theme-select');
    if (!sel) return;
    sel.value = id;
    sel.addEventListener('change', e => applyTheme(e.target.value));
  }
  const ThemeKit = { THEMES, applyTheme, renderThemeSelector, mountThemeSelector };
  global.ThemeKit = ThemeKit;
  if (typeof module !== 'undefined' && module.exports) module.exports = ThemeKit;
})(typeof window !== 'undefined' ? window : globalThis);
