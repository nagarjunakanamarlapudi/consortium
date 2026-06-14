/* ==========================================================================
   device-selector.js — Device profile registry + dropdown wiring
   ==========================================================================
   Defines 9 popular mobile device profiles. Applies one to <body> via
   CSS custom properties + data-attributes that drive phone-frame.css /
   devices.css.

   Usage in your feature HTML:
     1. Include a dropdown with id="device-select" inside the legend
        (the framework's renderDeviceSelector() returns the HTML)
     2. After your render() runs, call mountDeviceSelector('iphone-17-pro-max')
        to set the default device + wire up change events

   Notch types: 'island' | 'notch' | 'hole' | 'none'
   Bottom types: 'indicator' (modern iOS) | 'gesture-bar' (Android) | 'home-button' (older iOS)
   ========================================================================== */

const DEVICES = {
  /* ---------- Apple ---------- */
  'iphone-17-pro-max': {
    name: 'iPhone 17 Pro Max', os: 'ios', family: 'apple-flagship', surface: 'phone',
    width: 440, height: 956, radius: 55,
    notch: { type: 'island', w: 27.7, top: 11 },
    bottom: 'indicator',
    statusH: 59, bottomH: 34,
  },
  'iphone-17-pro': {
    name: 'iPhone 17 Pro', os: 'ios', family: 'apple-flagship', surface: 'phone',
    width: 402, height: 874, radius: 50,
    notch: { type: 'island', w: 30.4, top: 11 },
    bottom: 'indicator',
    statusH: 59, bottomH: 34,
  },
  'iphone-17': {
    name: 'iPhone 17', os: 'ios', family: 'apple', surface: 'phone',
    width: 393, height: 852, radius: 47,
    notch: { type: 'island', w: 31, top: 11 },
    bottom: 'indicator',
    statusH: 59, bottomH: 34,
  },
  'iphone-air': {
    name: 'iPhone Air', os: 'ios', family: 'apple', surface: 'phone',
    width: 393, height: 852, radius: 47,
    notch: { type: 'island', w: 31, top: 11 },
    bottom: 'indicator',
    statusH: 59, bottomH: 34,
  },
  'iphone-11-pro': {
    name: 'iPhone X / 11 Pro', os: 'ios', family: 'apple-legacy', surface: 'phone',
    width: 375, height: 812, radius: 39,
    notch: { type: 'notch', w: 55.7, h: 30 },
    bottom: 'indicator',
    statusH: 44, bottomH: 34,
  },
  'iphone-se': {
    name: 'iPhone SE (4th gen)', os: 'ios', family: 'apple-compact', surface: 'phone',
    width: 375, height: 667, radius: 6,
    notch: { type: 'none' },
    bottom: 'home-button',
    statusH: 20, bottomH: 0,
  },

  /* ---------- Android ---------- */
  'pixel-9-pro': {
    name: 'Pixel 9 Pro', os: 'android', family: 'pixel', surface: 'phone',
    width: 412, height: 919, radius: 28,
    notch: { type: 'hole', w: 5.8, top: 12 },
    bottom: 'gesture-bar',
    statusH: 24, bottomH: 24,
  },
  'pixel-9': {
    name: 'Pixel 9', os: 'android', family: 'pixel', surface: 'phone',
    width: 412, height: 879, radius: 24,
    notch: { type: 'hole', w: 5.8, top: 12 },
    bottom: 'gesture-bar',
    statusH: 24, bottomH: 24,
  },
  'galaxy-s25-ultra': {
    name: 'Galaxy S25 Ultra', os: 'android', family: 'galaxy', surface: 'phone',
    width: 440, height: 957, radius: 32,
    notch: { type: 'hole', w: 5.5, top: 14 },
    bottom: 'gesture-bar',
    statusH: 28, bottomH: 24,
  },
  'galaxy-s25': {
    name: 'Galaxy S25', os: 'android', family: 'galaxy', surface: 'phone',
    width: 412, height: 916, radius: 28,
    notch: { type: 'hole', w: 5.8, top: 14 },
    bottom: 'gesture-bar',
    statusH: 28, bottomH: 24,
  },

  /* ---------- Tablets ---------- */
  'ipad-pro-13': { name: 'iPad Pro 13"', os: 'ios', family: 'ipad', surface: 'tablet',
    width: 1032, height: 1376, radius: 22, notch: { type: 'none' }, bottom: 'indicator', statusH: 24, bottomH: 20 },
  'ipad-pro-11': { name: 'iPad Pro 11"', os: 'ios', family: 'ipad', surface: 'tablet',
    width: 834, height: 1210, radius: 20, notch: { type: 'none' }, bottom: 'indicator', statusH: 24, bottomH: 20 },
  'ipad-mini': { name: 'iPad mini', os: 'ios', family: 'ipad', surface: 'tablet',
    width: 744, height: 1133, radius: 18, notch: { type: 'none' }, bottom: 'indicator', statusH: 24, bottomH: 20 },

  /* ---------- Foldables (open + cover) ---------- */
  'galaxy-z-fold': { name: 'Galaxy Z Fold (open)', os: 'android', family: 'fold', surface: 'foldable', fold: 'open',
    width: 884, height: 1104, radius: 18, notch: { type: 'hole', w: 4, top: 12 }, bottom: 'gesture-bar', statusH: 28, bottomH: 24 },
  'galaxy-z-fold-cover': { name: 'Galaxy Z Fold (cover)', os: 'android', family: 'fold', surface: 'foldable', fold: 'closed',
    width: 374, height: 880, radius: 24, notch: { type: 'hole', w: 5, top: 12 }, bottom: 'gesture-bar', statusH: 28, bottomH: 24 },
  'pixel-fold': { name: 'Pixel Fold (open)', os: 'android', family: 'fold', surface: 'foldable', fold: 'open',
    width: 840, height: 1080, radius: 18, notch: { type: 'hole', w: 4, top: 12 }, bottom: 'gesture-bar', statusH: 28, bottomH: 24 },
  'pixel-fold-cover': { name: 'Pixel Fold (cover)', os: 'android', family: 'fold', surface: 'foldable', fold: 'closed',
    width: 372, height: 800, radius: 20, notch: { type: 'hole', w: 5, top: 12 }, bottom: 'gesture-bar', statusH: 28, bottomH: 24 },

  /* ---------- Web breakpoints ---------- */
  'web-mobile':  { name: 'Web · 390', os: 'web', family: 'web', surface: 'web', width: 390,  height: 760, radius: 0, notch: { type: 'none' }, bottom: 'none', statusH: 0, bottomH: 0 },
  'web-tablet':  { name: 'Web · 768', os: 'web', family: 'web', surface: 'web', width: 768,  height: 900, radius: 0, notch: { type: 'none' }, bottom: 'none', statusH: 0, bottomH: 0 },
  'web-desktop': { name: 'Web · 1280', os: 'web', family: 'web', surface: 'web', width: 1280, height: 800, radius: 0, notch: { type: 'none' }, bottom: 'none', statusH: 0, bottomH: 0 },
  'web-wide':    { name: 'Web · 1440', os: 'web', family: 'web', surface: 'web', width: 1440, height: 900, radius: 0, notch: { type: 'none' }, bottom: 'none', statusH: 0, bottomH: 0 },
};

/**
 * Apply a device profile to <body>: sets CSS variables + data-attributes
 * that drive phone-frame.css and devices.css.
 */
function applyDevice(deviceId) {
  const d = DEVICES[deviceId];
  if (!d) { console.warn(`[device-selector] unknown device: ${deviceId}`); return; }
  const body = document.body;
  body.style.setProperty('--device-radius', d.radius + 'px');
  body.style.setProperty('--device-aspect', `${d.width} / ${d.height}`);
  body.style.setProperty('--device-status-h', d.statusH + 'px');
  body.style.setProperty('--device-bottom-h', d.bottomH + 'px');
  if (d.notch.type === 'island' || d.notch.type === 'hole') {
    body.style.setProperty('--device-notch-w', d.notch.w + '%');
    body.style.setProperty('--device-notch-top', (d.notch.top || 11) + 'px');
  } else if (d.notch.type === 'notch') {
    body.style.setProperty('--device-notch-w', d.notch.w + '%');
    body.style.setProperty('--device-notch-h', d.notch.h + 'px');
  }
  body.dataset.device = deviceId;
  body.dataset.notch = d.notch.type;
  body.dataset.bottom = d.bottom;
  body.dataset.os = d.os;
  body.dataset.surface = d.surface || 'phone';
  if (d.surface === 'foldable') body.dataset.fold = d.fold || 'open'; else delete body.dataset.fold;
  // emit event so feature pages can re-render device-dependent spec values
  window.dispatchEvent(new CustomEvent('devicechange', { detail: { id: deviceId, device: d } }));
}

/**
 * Returns the HTML for a device-selector dropdown. Place it inside the legend.
 * After mounting, call mountDeviceSelector(defaultId) to wire up change events.
 */
function renderDeviceSelector() {
  // Adding a new device with a new `family` value? Add a label here too,
  // otherwise the device will appear under its raw family key in the dropdown.
  const groups = {
    'apple-flagship': 'iPhone Pro / Pro Max',
    'apple': 'iPhone',
    'apple-compact': 'iPhone SE',
    'apple-legacy': 'iPhone X-series',
    'pixel': 'Pixel',
    'galaxy': 'Galaxy',
    'ipad': 'iPad',
    'fold': 'Foldable',
    'web': 'Web',
  };
  const grouped = {};
  Object.entries(DEVICES).forEach(([id, d]) => {
    if (!grouped[d.family]) grouped[d.family] = [];
    grouped[d.family].push({ id, ...d });
  });
  const optgroups = Object.entries(grouped).map(([family, items]) => `
    <optgroup label="${groups[family] || family}">
      ${items.map(d => `<option value="${d.id}">${d.name}</option>`).join('')}
    </optgroup>
  `).join('');
  return `<span class="device-select"><select id="device-select" aria-label="Device profile">${optgroups}</select></span>`;
}

/**
 * Wire up the device selector dropdown. Sets default + listens for change.
 * The page's render() will be called automatically on device change so
 * device-dependent values (e.g. spec table device row) update.
 */
function mountDeviceSelector(defaultId) {
  applyDevice(defaultId);
  const sel = document.getElementById('device-select');
  if (!sel) return;
  sel.value = defaultId;
  sel.addEventListener('change', e => {
    applyDevice(e.target.value);
    if (typeof render === 'function') render();
  });
}

if (typeof module !== 'undefined' && module.exports) module.exports = { DEVICES, applyDevice, renderDeviceSelector, mountDeviceSelector };
