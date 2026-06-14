# App Interactive Mocks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a distributable `app-interactive-mocks` skill inside the consortium plugin that generates one self-contained HTML file per feature *flow* — a walkable, multi-screen, multi-surface (phone/tablet/foldable/web) high-fidelity prototype with a 20+ theme gallery, drift-proof state catalog, accessibility audit, and execution-ready spec sections.

**Architecture:** A generalized, project-agnostic port of the Aadhaa `mobile-app-mocks` skill. The output is a single HTML file importing shared assets from `design/_framework/`. We **preserve** the proven framework's public APIs, CSS class names, globals, and load order (so the visual port is low-risk) and **add** three new browser modules (`router.js`, `flowmap.js`, `a11y.js`) plus a theme gallery (`themes.css` + `theme-selector.js`) and a surface-aware frame (`frame.css`). Pure logic in the new modules is exported via a UMD guard so a Node-based test can exercise it.

**Tech Stack:** HTML + CSS + vanilla JS (classic `<script>`, no build, opens from `file://`). No package manager. "Tests" = one bash assertion script (`scripts/app-mocks.test.sh`) that greps files and shells out to `node` (v24, already present) for pure-logic JS assertions, plus a Claude-driven browser-MCP verification task and a manual install-and-exercise task. This matches the repo's existing convention (`scripts/*.test.sh` + manual verification; see `docs/plans/2026-06-04-stage-0-1-spine.md`).

**Spec:** `docs/specs/2026-06-14-app-interactive-mocks-design.md`

**Source to port from:** `~/projects/Aadhaa/.claude/skills/mobile-app-mocks/` (framework/*, template.html, examples/notifications-inbox.html). Porting = copy the proven file, then apply the listed edits — never re-transcribe from memory.

**Plan location note:** saved under `docs/plans/` (repo convention) rather than the skill default `docs/superpowers/plans/`.

---

## Contracts (shared — keep identical across all tasks)

**Skill root:** `skills/app-interactive-mocks/` (referred to below as `<SKILL>`).

**Design-token CSS variables (preserve existing names exactly — from the source `tokens.css`):**
`--primary --primary-rgb --primary-600 --primary-soft --primary-tint --accent --accent-rgb --accent-soft --accent-deep --bg --card --hover --border --border-soft --text --text-2 --muted --error --error-soft --warning --warning-soft --success --success-soft --r-xs --r-sm --r-md --r-card --r-lg --r-pill --s-2xs … --s-4xl --display --body --mono --shadow-card --shadow-menu --shadow-phone`
(The spec mentioned `--surface`/`--surface-2`; we reconcile to the existing `--card`/`--hover` — no rename — to keep the CSS port faithful.)

**Preserved CSS classes / DOM hooks:** `.shell .hero .quickref .legend .playground .phone .phone-frame .phone-screen .catalog .themes .s .lead .tint` and the gesture row hooks `.digrow[data-id]`, `.row-wrap`, `swipe-anim`, `dragging`, `data-revealed`. Catalog tiles remain `.phone-frame[data-state]` (now optionally also `[data-screen]`).

**Preserved globals the generated page defines:** `state`, `render()`, `statusBar()`, `resetState()`, `toggleDark()`, `catalogScreen(stateName)`, and (for gestures) `deleteItem(id)` / `tapRow(id)` / optional `longPress(id)`.

**Preserved framework globals:** `I.<icon>` (icons), `gStart(e,id)` (gestures), `withTempState(mutate,renderFn)` / `mountCatalog(fn)` / `mountThemePair(fn)` / `jsAttr(v)` (state-swap), `DEVICES` / `applyDevice(id)` / `renderDeviceSelector()` / `mountDeviceSelector(id)` (devices), `devicechange` event.

**New framework globals (this plan adds):**
- `Router`: `registerScreen(id,{title,tab,render,links})`, `navigate(id,{mode})` (`mode` = `push|replace|modal|tab`), `back()`, `current()`, `stack()`, `getScreens()`, `mountTabBar(tabs)`, `mount(rootElId,defaultId)`, `_reduce(stack,action)` (pure). Emits `screenchange`.
- `Flowmap`: `deriveGraph(screens)` (pure → `{nodes,edges}`), `mount(hostElId)`.
- `A11y`: `hexToRgb(hex)`, `relLuminance(hex)`, `contrastRatio(a,b)`, `wcagLevel(ratio,{large})`, `auditTapTargets(rootEl,{min})`, `mountAudit(hostElId)`. Listens `themechange`.
- `ThemeKit`: `THEMES` (array of `{id,name}`, ≥20), `applyTheme(id)`, `renderThemeSelector()`, `mountThemeSelector(id)`. Emits `themechange`.

**Theme application:** `applyTheme(id)` sets `document.documentElement.dataset.theme = id`. `themes.css` defines light vars at `[data-theme="<id>"]` and dark vars at `[data-theme="<id>"] .phone-screen.dark, [data-theme="<id>"] .dark-tokens`. The neutral default lives in `tokens.css` (`:root` + `.phone-screen.dark, .dark-tokens`) and corresponds to theme id `neutral`.

**Surface model:** each `DEVICES` entry gains `surface: 'phone'|'tablet'|'foldable'|'web'`. `applyDevice` additionally sets `document.body.dataset.surface`. `frame.css` styles each surface off `body[data-surface="…"]`, keeping the `.phone-frame`/`.phone-screen` class names.

**Generated-file CSS load order:** `tokens.css → themes.css → frame.css → components.css → spec-styles.css`.
**Generated-file JS load order:** `icons.js → gestures.js → state-swap.js → device-selector.js → theme-selector.js → router.js → flowmap.js → a11y.js`.

**UMD guard (every new `framework/*.js` ends with this; no `document`/`window` access at top level):**
```js
if (typeof module !== 'undefined' && module.exports) module.exports = <PublicObject>;
```

---

## File structure (created/modified in this plan)

```
consortium/
├── scripts/app-mocks.test.sh                    # NEW — bash+node assertion suite
└── skills/app-interactive-mocks/
    ├── SKILL.md                                  # NEW (Task 12)
    ├── README.md                                 # NEW (Task 13)
    ├── template.html                             # NEW (Task 10)
    ├── framework/
    │   ├── tokens.css        # Task 2  (port + neutralize)
    │   ├── themes.css        # Task 3  (new, 20+ presets)
    │   ├── theme-selector.js # Task 3  (new)
    │   ├── frame.css         # Task 4  (merge phone-frame.css+devices.css + surfaces)
    │   ├── device-selector.js# Task 4  (port + surfaces)
    │   ├── components.css    # Task 5  (port + nav/tabbar/web-nav)
    │   ├── icons.js          # Task 5  (port + extra icons)
    │   ├── gestures.js       # Task 6  (port + optional long-press)
    │   ├── state-swap.js     # Task 6  (port + per-screen catalog)
    │   ├── spec-styles.css   # Task 7  (port + flowmap/a11y styles)
    │   ├── router.js         # Task 8  (new)
    │   ├── flowmap.js        # Task 9  (new)
    │   └── a11y.js           # Task 11 (new)
    └── examples/
        └── shop-flow.html    # Task 10 (new, full-fat example)
modified:
└── .claude-plugin/plugin.json + README.md       # Task 13 (discoverability)
```

---

## Task 1: Test-harness bootstrap + skill skeleton

**Files:**
- Create: `scripts/app-mocks.test.sh`
- Create (dirs): `skills/app-interactive-mocks/framework/`, `skills/app-interactive-mocks/examples/`

- [ ] **Step 1: Create the skill directories**

Run:
```bash
mkdir -p skills/app-interactive-mocks/framework skills/app-interactive-mocks/examples
```
Expected: (no output)

- [ ] **Step 2: Write the test harness `scripts/app-mocks.test.sh`**

```bash
#!/usr/bin/env bash
# Assertion suite for the app-interactive-mocks skill.
# Greps skill files for required content and shells out to `node` for pure JS logic.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKILL="$ROOT/skills/app-interactive-mocks"
FW="$SKILL/framework"
fails=0

check() { # check "desc" "expected substring" "actual"
  if printf '%s' "$3" | grep -qF -- "$2"; then printf 'ok   - %s\n' "$1"
  else printf 'FAIL - %s\n      expected to contain: %s\n      got: %s\n' "$1" "$2" "$3"; fails=$((fails+1)); fi
}
checkge() { # checkge "desc" min actual  -> actual >= min (numeric)
  if [ "$3" -ge "$2" ] 2>/dev/null; then printf 'ok   - %s (%s >= %s)\n' "$1" "$3" "$2"
  else printf 'FAIL - %s: got %s, want >= %s\n' "$1" "$3" "$2"; fails=$((fails+1)); fi
}
jeval() { node -e "$1" 2>&1; }  # run a node expression, capture stdout+stderr

# ---- Task 1: skeleton ----
check "skill dir exists" "app-interactive-mocks" "$(ls "$ROOT/skills")"
[ -d "$FW" ] && echo "ok   - framework dir exists" || { echo "FAIL - framework dir missing"; fails=$((fails+1)); }

# (Later tasks append their assertion blocks below this line.)

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
```

- [ ] **Step 3: Run the suite to confirm the harness works and passes for Task 1**

Run: `bash scripts/app-mocks.test.sh`
Expected: lines `ok - skill dir exists` and `ok - framework dir exists`; final line `0 failure(s)`; exit 0.

- [ ] **Step 4: Commit**

```bash
git add scripts/app-mocks.test.sh skills/app-interactive-mocks
git commit -m "test: app-interactive-mocks harness + skill skeleton"
```

---

## Task 2: `tokens.css` — neutral, project-agnostic defaults

**Files:**
- Create: `skills/app-interactive-mocks/framework/tokens.css`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append the failing assertions to `scripts/app-mocks.test.sh`** (before the `printf '\n%s failure(s)'` line)

```bash
# ---- Task 2: tokens ----
check "tokens defines --primary"     "--primary:"  "$(cat "$FW/tokens.css" 2>/dev/null)"
check "tokens defines --card"        "--card:"     "$(cat "$FW/tokens.css" 2>/dev/null)"
check "tokens defines --display"     "--display:"  "$(cat "$FW/tokens.css" 2>/dev/null)"
check "tokens has neutral font"      "system-ui"   "$(cat "$FW/tokens.css" 2>/dev/null)"
check "tokens has dark block"        ".dark-tokens" "$(cat "$FW/tokens.css" 2>/dev/null)"
check "tokens is NOT Aadhaa teal"    "" "$(grep -c '#2FA39A' "$FW/tokens.css" 2>/dev/null | grep -x 0 && echo OK_NO_TEAL)"
```
(The last line asserts the Aadhaa teal `#2FA39A` count is `0`, printing `OK_NO_TEAL`.)

- [ ] **Step 2: Run to verify failure**

Run: `bash scripts/app-mocks.test.sh`
Expected: the Task 2 checks FAIL (`tokens.css` absent); failures > 0.

- [ ] **Step 3: Create `tokens.css` — copy the source then neutralize the brand**

Copy the proven file:
```bash
cp ~/projects/Aadhaa/.claude/skills/mobile-app-mocks/framework/tokens.css "$PWD/skills/app-interactive-mocks/framework/tokens.css"
```
Then edit `skills/app-interactive-mocks/framework/tokens.css`, replacing **only** the brand/typography values (keep every variable name and the dark block structure). Apply these exact replacements in `:root`:

```css
  --primary: #4F46E5;            /* indigo-600 */
  --primary-rgb: 79, 70, 229;
  --primary-600: #4338CA;
  --primary-soft: #E8E7FB;
  --primary-tint: #F4F3FE;

  --accent: #F59E0B;             /* amber-500 */
  --accent-rgb: 245, 158, 11;
  --accent-soft: #FEF3C7;
  --accent-deep: #92400E;

  --bg: #F7F7F9;
  --card: #FFFFFF;
  --hover: #F1F1F5;
  --border: #E5E5EC;

  --display: system-ui, -apple-system, 'Segoe UI', 'Inter', sans-serif;
  --body: system-ui, -apple-system, 'Segoe UI', 'Inter', sans-serif;
```
And in the `.phone-screen.dark, .dark-tokens` block, replace the primary overrides:
```css
  --primary: #818CF8;            /* indigo-400 for dark surfaces */
  --primary-rgb: 129, 140, 248;
  --primary-600: #A5B4FC;
  --primary-soft: rgba(129,140,248,.16);
  --primary-tint: rgba(129,140,248,.06);
```
Also update the file's top comment from "for mobile-app-mocks" to "for app-interactive-mocks". Leave radii, spacing, semantic colours, shadows, and all variable names unchanged.

- [ ] **Step 4: Run to verify pass**

Run: `bash scripts/app-mocks.test.sh`
Expected: all Task 1–2 checks `ok`; `0 failure(s)`.

- [ ] **Step 5: Commit**

```bash
git add skills/app-interactive-mocks/framework/tokens.css scripts/app-mocks.test.sh
git commit -m "feat: neutral project-agnostic tokens for app-interactive-mocks"
```

---

## Task 3: `themes.css` (20+ gallery) + `theme-selector.js`

**Files:**
- Create: `skills/app-interactive-mocks/framework/themes.css`
- Create: `skills/app-interactive-mocks/framework/theme-selector.js`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions**

```bash
# ---- Task 3: themes + theme-selector ----
node --check "$FW/theme-selector.js" >/dev/null 2>&1 && echo "ok   - theme-selector.js parses" || { echo "FAIL - theme-selector.js syntax"; fails=$((fails+1)); }
checkge "themes.css has >=20 [data-theme] blocks" 20 "$(grep -c '\[data-theme=' "$FW/themes.css" 2>/dev/null || echo 0)"
checkge "ThemeKit.THEMES has >=20 entries" 20 "$(jeval "console.log(require('$FW/theme-selector.js').THEMES.length)")"
# every THEMES id must have a matching selector in themes.css (or be 'neutral', defined in tokens.css)
check "every theme id is defined in CSS" "ALL_THEMES_DEFINED" "$(jeval "
  const fs=require('fs');
  const css=fs.readFileSync('$FW/themes.css','utf8');
  const ids=require('$FW/theme-selector.js').THEMES.map(t=>t.id).filter(id=>id!=='neutral');
  const missing=ids.filter(id=>!css.includes('[data-theme=\"'+id+'\"]'));
  console.log(missing.length? 'MISSING:'+missing.join(',') : 'ALL_THEMES_DEFINED');
")"
```

- [ ] **Step 2: Run to verify failure**

Run: `bash scripts/app-mocks.test.sh`
Expected: Task 3 checks FAIL (files absent).

- [ ] **Step 3: Write `theme-selector.js`**

```js
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
```

- [ ] **Step 4: Write `themes.css`** — one block per non-neutral theme id above.

Each theme overrides at minimum the brand + surface + text tokens for light, and the same for dark. Use this exact shape (shown for `indigo`, `teal`, `nord`, `dracula`); expand the remaining ids from the seed table below using the identical structure:

```css
/* themes.css — gallery presets. Applied via <html data-theme="…">.
   Light vars on [data-theme=X]; dark vars on [data-theme=X] .phone-screen.dark, [data-theme=X] .dark-tokens.
   Only brand/surface/text tokens vary; radii/spacing/type inherit from tokens.css. */

[data-theme="indigo"] { --primary:#4F46E5; --primary-rgb:79,70,229; --primary-600:#4338CA; --primary-soft:#E8E7FB; --primary-tint:#F4F3FE; --accent:#F59E0B; }
[data-theme="indigo"] .phone-screen.dark, [data-theme="indigo"] .dark-tokens { --primary:#818CF8; --primary-600:#A5B4FC; --primary-soft:rgba(129,140,248,.16); }

[data-theme="teal"] { --primary:#0D9488; --primary-rgb:13,148,136; --primary-600:#0F766E; --primary-soft:#CCFBF1; --primary-tint:#F0FDFA; --accent:#F59E0B; }
[data-theme="teal"] .phone-screen.dark, [data-theme="teal"] .dark-tokens { --primary:#2DD4BF; --primary-600:#5EEAD4; --primary-soft:rgba(45,212,191,.16); }

[data-theme="nord"] { --primary:#5E81AC; --primary-rgb:94,129,172; --primary-600:#81A1C1; --primary-soft:#E5E9F0; --primary-tint:#ECEFF4; --accent:#EBCB8B; --bg:#ECEFF4; --card:#FFFFFF; --text:#2E3440; --muted:#4C566A; --border:#D8DEE9; }
[data-theme="nord"] .phone-screen.dark, [data-theme="nord"] .dark-tokens { --bg:#2E3440; --card:#3B4252; --hover:#434C5E; --text:#ECEFF4; --text-2:#D8DEE9; --muted:#9aa4b8; --border:rgba(236,239,244,.10); --primary:#88C0D0; --primary-600:#8FBCBB; --primary-soft:rgba(136,192,208,.16); }

[data-theme="dracula"] { --primary:#BD93F9; --primary-rgb:189,147,249; --primary-600:#9F7AEA; --primary-soft:#EFE7FE; --primary-tint:#F7F3FE; --accent:#FFB86C; --bg:#F5F3FB; --card:#FFFFFF; --text:#282A36; --muted:#6272A4; --border:#E3E0F0; }
[data-theme="dracula"] .phone-screen.dark, [data-theme="dracula"] .dark-tokens { --bg:#282A36; --card:#343746; --hover:#3C3F51; --text:#F8F8F2; --text-2:#D8D8E0; --muted:#9aa0c0; --border:rgba(248,248,242,.10); --primary:#BD93F9; --primary-600:#D6BCFA; --primary-soft:rgba(189,147,249,.18); --accent:#FFB86C; }
```

**Seed table for the remaining ids** (light `--primary` / `--primary-600` / `--primary-soft` · `--accent` · dark `--primary` / `--primary-600`). Expand each row into the same two-selector block as above (add `--bg/--card/--text/--muted/--border` overrides only for the named-aesthetic rows that imply a full palette — `material-you, ios, solarized, catppuccin, tokyo-night, rose-pine, gruvbox, one-dark`; the plain hue rows just override the brand tokens):

| id | primary / 600 / soft (light) | accent | primary / 600 (dark) |
|---|---|---|---|
| emerald | `#059669` / `#047857` / `#D1FAE5` | `#F59E0B` | `#34D399` / `#6EE7B7` |
| rose | `#E11D48` / `#BE123C` / `#FFE4E6` | `#F59E0B` | `#FB7185` / `#FDA4AF` |
| amber | `#D97706` / `#B45309` / `#FEF3C7` | `#4F46E5` | `#FBBF24` / `#FCD34D` |
| violet | `#7C3AED` / `#6D28D9` / `#EDE9FE` | `#F59E0B` | `#A78BFA` / `#C4B5FD` |
| sky | `#0284C7` / `#0369A1` / `#E0F2FE` | `#F59E0B` | `#38BDF8` / `#7DD3FC` |
| orange | `#EA580C` / `#C2410C` / `#FFEDD5` | `#0D9488` | `#FB923C` / `#FDBA74` |
| crimson | `#DC2626` / `#B91C1C` / `#FEE2E2` | `#F59E0B` | `#F87171` / `#FCA5A5` |
| cyan | `#0891B2` / `#0E7490` / `#CFFAFE` | `#F59E0B` | `#22D3EE` / `#67E8F9` |
| lime | `#65A30D` / `#4D7C0F` / `#ECFCCB` | `#7C3AED` | `#A3E635` / `#BEF264` |
| fuchsia | `#C026D3` / `#A21CAF` / `#FAE8FF` | `#F59E0B` | `#E879F9` / `#F0ABFC` |
| slate | `#475569` / `#334155` / `#E2E8F0` | `#0EA5E9` | `#94A3B8` / `#CBD5E1` |
| material-you | `#6750A4` / `#4F378B` / `#EADDFF` | `#7D5260` | `#D0BCFF` / `#E8DEF8` |
| ios | `#007AFF` / `#0040DD` / `#D6E8FF` | `#FF9500` | `#0A84FF` / `#409CFF` |
| solarized | `#268BD2` / `#2076C2` / `#E8EEDF` (bg `#FDF6E3`, card `#FFFFFF`, text `#586E75`, border `#EEE8D5`) | `#B58900` | `#268BD2` / `#52A8E0` (bg `#002B36`, card `#073642`, text `#EEE8D5`, muted `#93A1A1`) |
| catppuccin | `#8839EF` / `#7287FD` / `#E9E2F3` (bg `#EFF1F5`, card `#FFFFFF`, text `#4C4F69`, border `#DCE0E8`) | `#EA76CB` | `#CBA6F7` / `#B4BEFE` (bg `#1E1E2E`, card `#28283D`, text `#CDD6F4`, muted `#9399B2`) |
| tokyo-night | `#3D59A1` / `#2E4480` / `#DDE2F2` (bg `#E1E2E7`, card `#FFFFFF`, text `#343B58`, border `#CDD0DA`) | `#FF9E64` | `#7AA2F7` / `#9AB8FF` (bg `#1A1B26`, card `#24283B`, text `#C0CAF5`, muted `#9AA5CE`) |
| rose-pine | `#907AA9` / `#7C6797` / `#EFE6F2` (bg `#FAF4ED`, card `#FFFFFF`, text `#575279`, border `#E8DCD5`) | `#D7827E` | `#C4A7E7` / `#D6BFF0` (bg `#191724`, card `#26233A`, text `#E0DEF4`, muted `#908CAA`) |
| gruvbox | `#B57614` / `#9C5E0E` / `#F4E8C8` (bg `#FBF1C7`, card `#FFFFFF`, text `#3C3836`, border `#EBDBB2`) | `#427B58` | `#FABD2F` / `#FAD55F` (bg `#282828`, card `#3C3836`, text `#EBDBB2`, muted `#A89984`) |
| one-dark | `#4078F2` / `#2F66E0` / `#DCE6FE` (bg `#FAFAFA`, card `#FFFFFF`, text `#383A42`, border `#E5E5E6`) | `#C18401` | `#61AFEF` / `#82C0FF` (bg `#282C34`, card `#31353F`, text `#ABB2BF`, muted `#828997`) |

(`material-you` and `ios` are hue-only rows. Every dark block also adds `--primary-soft:rgba(<dark primary rgb>,.16)`.)

- [ ] **Step 5: Run to verify pass**

Run: `bash scripts/app-mocks.test.sh`
Expected: Task 3 checks `ok` — `>=20 [data-theme] blocks`, `THEMES has >=20`, `ALL_THEMES_DEFINED`; `0 failure(s)`.

- [ ] **Step 6: Commit**

```bash
git add skills/app-interactive-mocks/framework/themes.css skills/app-interactive-mocks/framework/theme-selector.js scripts/app-mocks.test.sh
git commit -m "feat: 20+ theme gallery + live theme selector"
```

---

## Task 4: `frame.css` (surface-aware) + `device-selector.js` (surfaces)

**Files:**
- Create: `skills/app-interactive-mocks/framework/frame.css`
- Create: `skills/app-interactive-mocks/framework/device-selector.js`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions**

```bash
# ---- Task 4: frame + devices/surfaces ----
node --check "$FW/device-selector.js" >/dev/null 2>&1 && echo "ok   - device-selector.js parses" || { echo "FAIL - device-selector.js syntax"; fails=$((fails+1)); }
check "frame.css styles web surface"      'data-surface="web"'      "$(cat "$FW/frame.css" 2>/dev/null)"
check "frame.css styles foldable surface" 'data-surface="foldable"' "$(cat "$FW/frame.css" 2>/dev/null)"
check "frame.css keeps .phone-frame class" ".phone-frame" "$(cat "$FW/frame.css" 2>/dev/null)"
check "registry has a tablet surface"   "surface: 'tablet'"   "$(cat "$FW/device-selector.js" 2>/dev/null)"
check "registry has a foldable surface" "surface: 'foldable'" "$(cat "$FW/device-selector.js" 2>/dev/null)"
check "registry has a web surface"      "surface: 'web'"      "$(cat "$FW/device-selector.js" 2>/dev/null)"
check "applyDevice sets data-surface"   "dataset.surface"     "$(cat "$FW/device-selector.js" 2>/dev/null)"
checkge "registry has >=15 devices" 15 "$(jeval "console.log(Object.keys(require('$FW/device-selector.js').DEVICES).length)")"
```

- [ ] **Step 2: Run to verify failure**

Run: `bash scripts/app-mocks.test.sh`
Expected: Task 4 checks FAIL.

- [ ] **Step 3: Create `frame.css` by merging the two source files, then add surfaces**

```bash
cat ~/projects/Aadhaa/.claude/skills/mobile-app-mocks/framework/phone-frame.css \
    ~/projects/Aadhaa/.claude/skills/mobile-app-mocks/framework/devices.css \
    > "$PWD/skills/app-interactive-mocks/framework/frame.css"
```
Then append the surface rules to `frame.css` (phones already covered by the merged content; these add tablet/foldable/web — all keyed off `body[data-surface]`, all reusing `.phone-frame`/`.phone-screen`):

```css
/* ===== surfaces (added for app-interactive-mocks) ===== */
/* tablet: larger min-radius, optional landscape via data-orientation */
body[data-surface="tablet"] .phone-frame { border-width: 10px; }
body[data-surface="tablet"][data-orientation="landscape"] .phone { transform: none; }

/* foldable: hinge crease when open; closed behaves like a phone */
body[data-surface="foldable"][data-fold="open"] .phone-screen {
  background-image: linear-gradient(90deg, transparent calc(50% - 1px), rgba(0,0,0,.12) 50%, transparent calc(50% + 1px));
}

/* web: browser chrome (traffic lights + URL bar) above the screen */
body[data-surface="web"] .phone-frame { border-radius: 10px; border-width: 0; box-shadow: var(--shadow-card); overflow: hidden; }
body[data-surface="web"] .phone-screen { border-radius: 0; }
body[data-surface="web"] .phone-frame::before {
  content: "";
  display: block; height: 38px; background: var(--hover);
  border-bottom: 1px solid var(--border);
  background-image:
    radial-gradient(circle 5px at 16px 19px, #ff5f57 50%, transparent 51%),
    radial-gradient(circle 5px at 34px 19px, #febc2e 50%, transparent 51%),
    radial-gradient(circle 5px at 52px 19px, #28c840 50%, transparent 51%);
}
```
(If `phone-frame.css` sizes the frame via `aspect-ratio: var(--device-aspect)`, the web `::before` chrome adds height on top — acceptable for the mock. Verify visually in Task 14.)

- [ ] **Step 4: Create `device-selector.js` — copy the source, then add `surface` + new profiles**

```bash
cp ~/projects/Aadhaa/.claude/skills/mobile-app-mocks/framework/device-selector.js "$PWD/skills/app-interactive-mocks/framework/device-selector.js"
```
Apply these edits to `device-selector.js`:

1. Add `surface: 'phone',` to **every** existing entry in `DEVICES` (the 9 phones).
2. Add these new entries inside the `DEVICES` object (after the Android phones):
```js
  /* ---------- Tablets ---------- */
  'ipad-pro-13': { name: 'iPad Pro 13"', os: 'ios', family: 'ipad', surface: 'tablet',
    width: 1032, height: 1376, radius: 22, notch: { type: 'none' }, bottom: 'indicator', statusH: 24, bottomH: 20 },
  'ipad-pro-11': { name: 'iPad Pro 11"', os: 'ios', family: 'ipad', surface: 'tablet',
    width: 834, height: 1210, radius: 20, notch: { type: 'none' }, bottom: 'indicator', statusH: 24, bottomH: 20 },
  'ipad-mini': { name: 'iPad mini', os: 'ios', family: 'ipad', surface: 'tablet',
    width: 744, height: 1133, radius: 18, notch: { type: 'none' }, bottom: 'indicator', statusH: 24, bottomH: 20 },
  /* ---------- Foldables (open) ---------- */
  'galaxy-z-fold': { name: 'Galaxy Z Fold (open)', os: 'android', family: 'fold', surface: 'foldable',
    width: 884, height: 1104, radius: 18, notch: { type: 'hole', w: 4, top: 12 }, bottom: 'gesture-bar', statusH: 28, bottomH: 24 },
  'pixel-fold': { name: 'Pixel Fold (open)', os: 'android', family: 'fold', surface: 'foldable',
    width: 840, height: 1080, radius: 18, notch: { type: 'hole', w: 4, top: 12 }, bottom: 'gesture-bar', statusH: 28, bottomH: 24 },
  /* ---------- Web breakpoints ---------- */
  'web-mobile':  { name: 'Web · 390', os: 'web', family: 'web', surface: 'web', width: 390,  height: 760, radius: 0, notch: { type: 'none' }, bottom: 'none', statusH: 0, bottomH: 0 },
  'web-tablet':  { name: 'Web · 768', os: 'web', family: 'web', surface: 'web', width: 768,  height: 900, radius: 0, notch: { type: 'none' }, bottom: 'none', statusH: 0, bottomH: 0 },
  'web-desktop': { name: 'Web · 1280', os: 'web', family: 'web', surface: 'web', width: 1280, height: 800, radius: 0, notch: { type: 'none' }, bottom: 'none', statusH: 0, bottomH: 0 },
  'web-wide':    { name: 'Web · 1440', os: 'web', family: 'web', surface: 'web', width: 1440, height: 900, radius: 0, notch: { type: 'none' }, bottom: 'none', statusH: 0, bottomH: 0 },
```
3. In `applyDevice(deviceId)`, add this line right after `body.dataset.os = d.os;`:
```js
  body.dataset.surface = d.surface || 'phone';
```
4. In `renderDeviceSelector()`, extend the `groups` map with the new families:
```js
    'ipad': 'iPad',
    'fold': 'Foldable',
    'web': 'Web',
```
5. At the **end of the file**, add the UMD export (so the registry is node-testable):
```js
if (typeof module !== 'undefined' && module.exports) module.exports = { DEVICES, applyDevice, renderDeviceSelector, mountDeviceSelector };
```

- [ ] **Step 5: Run to verify pass**

Run: `bash scripts/app-mocks.test.sh`
Expected: Task 4 checks `ok`; `registry has >=15 devices` (9 + 9 = 18); `0 failure(s)`.

- [ ] **Step 6: Commit**

```bash
git add skills/app-interactive-mocks/framework/frame.css skills/app-interactive-mocks/framework/device-selector.js scripts/app-mocks.test.sh
git commit -m "feat: surface-aware frame + tablet/foldable/web device profiles"
```

---

## Task 5: `components.css` (+ nav/tabbar/web-nav) + `icons.js` (+ icons)

**Files:**
- Create: `skills/app-interactive-mocks/framework/components.css`
- Create: `skills/app-interactive-mocks/framework/icons.js`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions**

```bash
# ---- Task 5: components + icons ----
node --check "$FW/icons.js" >/dev/null 2>&1 && echo "ok   - icons.js parses" || { echo "FAIL - icons.js syntax"; fails=$((fails+1)); }
check "components has .tabbar" ".tabbar" "$(cat "$FW/components.css" 2>/dev/null)"
check "components has .appbar" ".appbar" "$(cat "$FW/components.css" 2>/dev/null)"
check "icons exports I global"  "var I" "$(cat "$FW/icons.js" 2>/dev/null)$(grep -c 'I *=' "$FW/icons.js" 2>/dev/null)"
check "icons has chevron"  "chevron" "$(cat "$FW/icons.js" 2>/dev/null)"
```

- [ ] **Step 2: Run to verify failure** — `bash scripts/app-mocks.test.sh` → Task 5 FAIL.

- [ ] **Step 3: Port both files, then extend**

```bash
cp ~/projects/Aadhaa/.claude/skills/mobile-app-mocks/framework/components.css "$PWD/skills/app-interactive-mocks/framework/components.css"
cp ~/projects/Aadhaa/.claude/skills/mobile-app-mocks/framework/icons.js       "$PWD/skills/app-interactive-mocks/framework/icons.js"
```
Append to `components.css` (cross-surface chrome used by the router):
```css
/* ===== nav chrome (added for app-interactive-mocks) ===== */
.tabbar { position: sticky; bottom: 0; display: flex; background: var(--card); border-top: 1px solid var(--border); }
.tabbar .tab { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px 0 calc(8px + var(--device-bottom-h, 0px)); background: none; border: 0; color: var(--muted); font: inherit; cursor: pointer; min-height: 44px; }
.tabbar .tab.on { color: var(--primary); }
.tabbar .tab-lbl { font-size: 11px; }
.navbar-back { display: inline-flex; align-items: center; gap: 4px; background: none; border: 0; color: var(--primary); font: inherit; cursor: pointer; min-height: 44px; padding: 0 8px; }
.web-topnav { display: flex; gap: 16px; align-items: center; padding: 10px 16px; border-bottom: 1px solid var(--border); }
/* screen transition layers */
.scr { will-change: transform, opacity; }
@media (prefers-reduced-motion: no-preference) {
  .scr-push { animation: scrPush .28s cubic-bezier(.2,.75,.25,1); }
  .scr-pop  { animation: scrPop  .26s cubic-bezier(.2,.75,.25,1); }
  .scr-modal{ animation: scrModal .30s cubic-bezier(.2,.75,.25,1); }
}
@keyframes scrPush { from { transform: translateX(28px); opacity: 0; } to { transform: none; opacity: 1; } }
@keyframes scrPop  { from { transform: translateX(-20px); opacity: 0; } to { transform: none; opacity: 1; } }
@keyframes scrModal{ from { transform: translateY(40px); opacity: 0; } to { transform: none; opacity: 1; } }
```
Edit `icons.js`: ensure the icon object is exposed as a global named `I` (the source already does — keep it). Add these keys to the `I` object (SVG strings, 24×24, `stroke="currentColor"` `fill="none"` `stroke-width="2"` to match the existing style):
```js
  chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6"/></svg>',
  back:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 6l-6 6 6 6"/></svg>',
  home:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 11l9-8 9 8M5 10v10h14V10"/></svg>',
  search:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg>',
  cart:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M3 4h2l2.4 12h11l1.6-8H6"/></svg>',
  user:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>',
```
(Add them inside the existing `I = { … }` literal; if the source ends the object before a closing `;`, insert before the closing brace.)

- [ ] **Step 4: Run to verify pass** — `bash scripts/app-mocks.test.sh` → Task 5 `ok`; `0 failure(s)`.

- [ ] **Step 5: Commit**

```bash
git add skills/app-interactive-mocks/framework/components.css skills/app-interactive-mocks/framework/icons.js scripts/app-mocks.test.sh
git commit -m "feat: nav/tabbar/web-nav primitives + transition + nav icons"
```

---

## Task 6: `gestures.js` (+ long-press) + `state-swap.js` (+ per-screen catalog)

**Files:**
- Create: `skills/app-interactive-mocks/framework/gestures.js`
- Create: `skills/app-interactive-mocks/framework/state-swap.js`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions**

```bash
# ---- Task 6: gestures + state-swap ----
node --check "$FW/gestures.js"   >/dev/null 2>&1 && echo "ok   - gestures.js parses"   || { echo "FAIL - gestures.js syntax";   fails=$((fails+1)); }
node --check "$FW/state-swap.js" >/dev/null 2>&1 && echo "ok   - state-swap.js parses" || { echo "FAIL - state-swap.js syntax"; fails=$((fails+1)); }
check "gestures supports long-press" "longPress" "$(cat "$FW/gestures.js" 2>/dev/null)"
check "state-swap keeps withTempState" "function withTempState" "$(cat "$FW/state-swap.js" 2>/dev/null)"
check "catalog supports data-screen"   "data-screen"            "$(cat "$FW/state-swap.js" 2>/dev/null)"
```

- [ ] **Step 2: Run to verify failure** — `bash scripts/app-mocks.test.sh` → Task 6 FAIL.

- [ ] **Step 3: Port both, then extend**

```bash
cp ~/projects/Aadhaa/.claude/skills/mobile-app-mocks/framework/gestures.js   "$PWD/skills/app-interactive-mocks/framework/gestures.js"
cp ~/projects/Aadhaa/.claude/skills/mobile-app-mocks/framework/state-swap.js "$PWD/skills/app-interactive-mocks/framework/state-swap.js"
```
Edit `gestures.js` — add optional long-press. In `gStart(e, id)`, after `drag = { … };`, add:
```js
  drag.lpTimer = setTimeout(() => {
    if (drag && drag.axis === null && Math.abs(drag.dx) < 8 && Math.abs(drag.dy) < 8) {
      if (typeof longPress === 'function') longPress(id);
      drag = null; // long-press consumes the gesture
    }
  }, 500);
```
In `gEnd()`, as the first line inside the function (after `if (!drag) return;`), add:
```js
  if (drag.lpTimer) clearTimeout(drag.lpTimer);
```
And in the `pointermove` handler, when movement is detected (inside the `if (Math.abs(dx) > 8 || Math.abs(dy) > 8)` branch), add `if (drag.lpTimer) { clearTimeout(drag.lpTimer); drag.lpTimer = null; }`.

Edit `state-swap.js` — make `mountCatalog` honor an optional `data-screen`. Replace the body of `mountCatalog` with:
```js
function mountCatalog(catalogFn) {
  document.querySelectorAll('.phone-frame[data-state]').forEach(frame => {
    const stateName = frame.dataset.state;
    const screenId = frame.dataset.screen; // optional — for multi-screen flows
    const screen = frame.querySelector('.phone-screen');
    if (!screen) return;
    screen.innerHTML = (catalogFn.length >= 2) ? catalogFn(stateName, screenId) : catalogFn(stateName);
  });
}
```
(Keeps the single-arg form working; passes `screenId` when the page's `catalogFn` declares a second parameter.)

- [ ] **Step 4: Run to verify pass** — `bash scripts/app-mocks.test.sh` → Task 6 `ok`; `0 failure(s)`.

- [ ] **Step 5: Commit**

```bash
git add skills/app-interactive-mocks/framework/gestures.js skills/app-interactive-mocks/framework/state-swap.js scripts/app-mocks.test.sh
git commit -m "feat: long-press gesture + per-screen catalog tiles"
```

---

## Task 7: `spec-styles.css` (+ flowmap/a11y styles)

**Files:**
- Create: `skills/app-interactive-mocks/framework/spec-styles.css`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions**

```bash
# ---- Task 7: spec-styles ----
check "spec-styles has .flowmap" ".flowmap" "$(cat "$FW/spec-styles.css" 2>/dev/null)"
check "spec-styles has .a11y"    ".a11y"    "$(cat "$FW/spec-styles.css" 2>/dev/null)"
check "spec-styles keeps .quickref" ".quickref" "$(cat "$FW/spec-styles.css" 2>/dev/null)"
```

- [ ] **Step 2: Run to verify failure** — `bash scripts/app-mocks.test.sh` → Task 7 FAIL.

- [ ] **Step 3: Port then extend**

```bash
cp ~/projects/Aadhaa/.claude/skills/mobile-app-mocks/framework/spec-styles.css "$PWD/skills/app-interactive-mocks/framework/spec-styles.css"
```
Append to `spec-styles.css`:
```css
/* ===== flow map (added for app-interactive-mocks) ===== */
.flowmap { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.fm-node { padding: 8px 14px; border: 1px solid var(--border); border-radius: var(--r-pill); background: var(--card); color: var(--text); font: inherit; cursor: pointer; }
.fm-node.on { border-color: var(--primary); color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }
.fm-edges { display: flex; flex-wrap: wrap; gap: 8px; width: 100%; margin-top: 8px; color: var(--muted); font-size: 12px; }
.fm-edge { padding: 2px 8px; background: var(--hover); border-radius: var(--r-sm); }
/* ===== accessibility audit ===== */
.a11y table { width: 100%; border-collapse: collapse; font-size: 13px; }
.a11y th, .a11y td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--border); }
.a11y .pass { color: var(--success); font-weight: 600; }
.a11y .fail { color: var(--error); font-weight: 600; }
.a11y .dyn { display: flex; gap: 16px; flex-wrap: wrap; }
```

- [ ] **Step 4: Run to verify pass** — `bash scripts/app-mocks.test.sh` → Task 7 `ok`.

- [ ] **Step 5: Commit**

```bash
git add skills/app-interactive-mocks/framework/spec-styles.css scripts/app-mocks.test.sh
git commit -m "feat: flow-map + a11y spec-section styling"
```

---

## Task 8: `router.js` (new — in-frame screen router)

**Files:**
- Create: `skills/app-interactive-mocks/framework/router.js`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions (pure reducer)**

```bash
# ---- Task 8: router ----
node --check "$FW/router.js" >/dev/null 2>&1 && echo "ok   - router.js parses" || { echo "FAIL - router.js syntax"; fails=$((fails+1)); }
check "push appends to stack"  "a,b"   "$(jeval "const R=require('$FW/router.js'); console.log(R._reduce(['a'],{type:'push',id:'b'}).join(','))")"
check "replace swaps top"      "a,c"   "$(jeval "const R=require('$FW/router.js'); console.log(R._reduce(['a','b'],{type:'replace',id:'c'}).join(','))")"
check "pop removes top"        "a"     "$(jeval "const R=require('$FW/router.js'); console.log(R._reduce(['a','b'],{type:'pop'}).join(','))")"
check "pop keeps root"         "a"     "$(jeval "const R=require('$FW/router.js'); console.log(R._reduce(['a'],{type:'pop'}).join(','))")"
check "tab resets to root"     "home"  "$(jeval "const R=require('$FW/router.js'); console.log(R._reduce(['a','b','c'],{type:'tab',id:'home'}).join(','))")"
```

- [ ] **Step 2: Run to verify failure** — `bash scripts/app-mocks.test.sh` → Task 8 FAIL.

- [ ] **Step 3: Write `router.js`**

```js
/* router.js — in-frame screen router for app-interactive-mocks.
   Swaps the active screen inside one .phone-screen; keeps a back-stack and tab bar.
   Pure reducer (_reduce) is node-testable. */
(function (global) {
  const screens = {};   // id -> {id,title,tab,render,links}
  let stack = [];       // screen ids; last = active
  let tabs = [];        // [{id,label,icon,screen}]
  let rootEl = null;

  function registerScreen(id, def) { screens[id] = Object.assign({ id, title: id, links: [] }, def); }
  function getScreens() { return screens; }
  function current() { return screens[stack[stack.length - 1]] || null; }
  function stackIds() { return stack.slice(); }

  // pure: given a stack + action, return the next stack
  function reduce(stk, action) {
    const s = stk.slice();
    switch (action.type) {
      case 'push':    s.push(action.id); return s;
      case 'replace': s[s.length - 1] = action.id; return s;
      case 'pop':     return s.length > 1 ? s.slice(0, -1) : s;
      case 'tab':     return [action.id];
      default:        return s;
    }
  }

  function renderTabBar() {
    if (!tabs.length) return '';
    const activeTab = (current() || {}).tab;
    return `<nav class="tabbar">${tabs.map(t =>
      `<button class="tab${t.id === activeTab ? ' on' : ''}" onclick="Router.navigate('${t.screen}',{mode:'tab'})">
         <span class="tab-ico">${t.icon || ''}</span><span class="tab-lbl">${t.label}</span>
       </button>`).join('')}</nav>`;
  }

  function paint(transition) {
    if (!rootEl) return;
    const scr = current();
    if (!scr) return;
    const ctx = {
      surface: document.body.dataset.surface || 'phone',
      theme: document.documentElement.dataset.theme || 'neutral',
      state: global.state,
      back: back, navigate: navigate,
    };
    const head = (typeof global.statusBar === 'function') ? global.statusBar() : '';
    rootEl.innerHTML = head + `<div class="scr ${transition || ''}">${scr.render(ctx)}</div>` + renderTabBar();
    global.dispatchEvent(new CustomEvent('screenchange', { detail: { id: scr.id, stack: stackIds() } }));
  }

  function navigate(id, opts) {
    opts = opts || {};
    const mode = opts.mode || 'push';
    if (!screens[id]) { console.warn('[router] unknown screen:', id); return; }
    const reduceType = (mode === 'modal') ? 'push' : mode;
    const transition = mode === 'push' ? 'scr-push' : mode === 'modal' ? 'scr-modal' : mode === 'pop' ? 'scr-pop' : '';
    stack = reduce(stack, { type: reduceType, id });
    paint(transition);
  }
  function back() {
    const before = stack.length;
    stack = reduce(stack, { type: 'pop' });
    if (stack.length !== before) paint('scr-pop');
  }
  function mountTabBar(t) { tabs = (t || []).slice(); }
  function mount(rootElId, defaultScreenId) {
    rootEl = document.getElementById(rootElId);
    stack = [defaultScreenId];
    paint('');
  }

  const Router = { registerScreen, getScreens, current, stack: stackIds, navigate, back, mountTabBar, mount, _reduce: reduce };
  global.Router = Router;
  if (typeof module !== 'undefined' && module.exports) module.exports = Router;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: Run to verify pass** — `bash scripts/app-mocks.test.sh` → all 5 reducer checks `ok`; `0 failure(s)`.

- [ ] **Step 5: Commit**

```bash
git add skills/app-interactive-mocks/framework/router.js scripts/app-mocks.test.sh
git commit -m "feat: in-frame screen router with back-stack + tabs"
```

---

## Task 9: `flowmap.js` (new — auto-derived screen graph)

**Files:**
- Create: `skills/app-interactive-mocks/framework/flowmap.js`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions (pure deriveGraph)**

```bash
# ---- Task 9: flowmap ----
node --check "$FW/flowmap.js" >/dev/null 2>&1 && echo "ok   - flowmap.js parses" || { echo "FAIL - flowmap.js syntax"; fails=$((fails+1)); }
check "deriveGraph yields nodes" "2" "$(jeval "const F=require('$FW/flowmap.js'); console.log(F.deriveGraph({a:{id:'a',links:['b']},b:{id:'b',links:[]}}).nodes.length)")"
check "deriveGraph yields edges" "a->b" "$(jeval "const F=require('$FW/flowmap.js'); const g=F.deriveGraph({a:{id:'a',links:['b']},b:{id:'b',links:[]}}); console.log(g.edges.map(e=>e.from+'->'+e.to).join(','))")"
check "deriveGraph drops dangling edges" "0" "$(jeval "const F=require('$FW/flowmap.js'); console.log(F.deriveGraph({a:{id:'a',links:['ghost']}}).edges.length)")"
```

- [ ] **Step 2: Run to verify failure** — `bash scripts/app-mocks.test.sh` → Task 9 FAIL.

- [ ] **Step 3: Write `flowmap.js`**

```js
/* flowmap.js — auto-derived screen graph for app-interactive-mocks.
   Nodes from Router screens; edges from each screen's declared `links`.
   Pure deriveGraph is node-testable. */
(function (global) {
  function deriveGraph(screens) {
    const nodes = Object.values(screens).map(s => ({ id: s.id, title: s.title || s.id }));
    const edges = [];
    Object.values(screens).forEach(s => (s.links || []).forEach(to => {
      if (screens[to]) edges.push({ from: s.id, to });
    }));
    return { nodes, edges };
  }
  function mount(hostElId) {
    const host = document.getElementById(hostElId);
    if (!host || !global.Router) return;
    function paint() {
      const { nodes, edges } = deriveGraph(global.Router.getScreens());
      const cur = (global.Router.current() || {}).id;
      host.innerHTML = `<div class="flowmap">
        ${nodes.map(n => `<button class="fm-node${n.id === cur ? ' on' : ''}" onclick="Router.navigate('${n.id}',{mode:'replace'})">${n.title}</button>`).join('')}
        <div class="fm-edges">${edges.map(e => `<span class="fm-edge">${e.from} &rarr; ${e.to}</span>`).join('')}</div>
      </div>`;
    }
    paint();
    global.addEventListener('screenchange', paint);
  }
  const Flowmap = { deriveGraph, mount };
  global.Flowmap = Flowmap;
  if (typeof module !== 'undefined' && module.exports) module.exports = Flowmap;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: Run to verify pass** — `bash scripts/app-mocks.test.sh` → Task 9 `ok`; `0 failure(s)`.

- [ ] **Step 5: Commit**

```bash
git add skills/app-interactive-mocks/framework/flowmap.js scripts/app-mocks.test.sh
git commit -m "feat: auto-derived flow map from screen links"
```

---

## Task 10: `template.html` + `examples/shop-flow.html`

**Files:**
- Create: `skills/app-interactive-mocks/template.html`
- Create: `skills/app-interactive-mocks/examples/shop-flow.html`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions**

```bash
# ---- Task 10: template + example ----
check "template loads themes.css"     "_framework/themes.css"        "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template loads router.js"      "_framework/router.js"         "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template loads flowmap.js"     "_framework/flowmap.js"        "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template loads a11y.js"        "_framework/a11y.js"           "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template registers a screen"   "registerScreen"               "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template mounts theme selector" "mountThemeSelector"          "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template mounts flow map"      "Flowmap.mount"                "$(cat "$SKILL/template.html" 2>/dev/null)"
check "example imports framework"     "_framework/router.js"         "$(cat "$SKILL/examples/shop-flow.html" 2>/dev/null)"
check "example registers >=3 screens" "" "$(c=$(grep -c 'registerScreen' "$SKILL/examples/shop-flow.html" 2>/dev/null||echo 0); [ "$c" -ge 3 ] && echo SCREENS_OK)"
check "example uses real images"      "images.unsplash.com"          "$(cat "$SKILL/examples/shop-flow.html" 2>/dev/null)"
```

- [ ] **Step 2: Run to verify failure** — `bash scripts/app-mocks.test.sh` → Task 10 FAIL.

- [ ] **Step 3: Write `template.html`** (flow-aware scaffold; preserves the source wiring, adds router/themes/flowmap/a11y)

```html
<!DOCTYPE html>
<html lang="en" data-theme="neutral">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title><!-- TODO: page title — e.g. "Checkout flow · spec · MyApp" --></title>
<!-- Framework CSS — order matters: tokens → themes → frame → components → spec -->
<link rel="stylesheet" href="_framework/tokens.css">
<link rel="stylesheet" href="_framework/themes.css">
<link rel="stylesheet" href="_framework/frame.css">
<link rel="stylesheet" href="_framework/components.css">
<link rel="stylesheet" href="_framework/spec-styles.css">
</head>
<body id="body">
<main class="shell">

  <header class="hero">
    <div>
      <div class="kicker"><span class="dot"></span> <!-- TODO: project · flow --></div>
      <h1><!-- TODO: flow name e.g. "Checkout.<br>Built for <span class='tint'>touch</span>." --></h1>
    </div>
    <div class="meta">
      <b>Spec for</b> · <!-- TODO: Flutter / SwiftUI / Compose / Web --><br>
      <b>Updated</b> · <!-- TODO: date --><br>
      <b>Status</b> · ready for execution
    </div>
  </header>

  <div class="quickref">
    <!-- TODO: 4 must-know values -->
    <div class="qr"><div class="k">Reference device</div><div class="v">iPhone 17 Pro Max</div><div class="vsub">switch via selector</div></div>
    <div class="qr"><div class="k">Min tap target</div><div class="v">44 × 44 pt</div><div class="vsub">audited below</div></div>
    <div class="qr"><div class="k">Key motion</div><div class="v">280 ms push</div><div class="vsub"><code>cubic-bezier(.2,.75,.25,1)</code></div></div>
    <div class="qr"><div class="k">Active theme</div><div class="v" id="qr-theme">Neutral</div><div class="vsub">switch via selector</div></div>
  </div>

  <div class="legend">
    <span class="title">Live state</span>
    <span id="legend-items" style="display:flex;gap:8px;flex-wrap:wrap;"></span>
    <button onclick="Router.back()">Back</button>
    <button class="dark-toggle" id="dark-btn" onclick="toggleDark()">Dark mode</button>
    <span id="theme-selector-host"></span>
    <span id="device-selector-host"></span>
  </div>

  <section class="s">
    <h2>Interactive <span class="tint">playground</span></h2>
    <p class="lead"><!-- TODO: 1-2 sentences: the flow + key gestures/navigation. --></p>
    <div class="playground">
      <div class="phone"><div class="phone-frame"><div class="phone-screen" id="screen"></div></div></div>
      <div class="annot"><div class="group"><div class="k">Navigation</div>
        <div class="row-spec"><span class="label">Tap item</span><span class="val">push detail</span></div>
        <div class="row-spec"><span class="label">Back</span><span class="val">pop</span></div>
        <div class="row-spec"><span class="label">Tabs</span><span class="val">switch root</span></div>
      </div></div>
    </div>
  </section>

  <section class="s">
    <h2>Flow <span class="tint">map</span></h2>
    <p class="lead">Auto-derived from screen links · click a node to jump.</p>
    <div id="flowmap-host"></div>
  </section>

  <section class="s">
    <h2>State <span class="tint">catalog</span></h2>
    <p class="lead">Frozen frames · same render path as the playground via state-swap.</p>
    <div class="catalog">
      <!-- TODO: one tile per (screen,state). data-screen optional. -->
      <div><div class="cap"><span class="dot"></span> home · default</div><div class="phone-frame" data-state="default" data-screen="home"><div class="phone-screen"></div></div></div>
      <div><div class="cap"><span class="dot warn"></span> home · loading</div><div class="phone-frame" data-state="loading" data-screen="home"><div class="phone-screen"></div></div></div>
      <div><div class="cap"><span class="dot dark"></span> home · dark</div><div class="phone-frame" data-state="default" data-screen="home"><div class="phone-screen dark"></div></div></div>
    </div>
  </section>

  <section class="s">
    <h2>Accessibility <span class="tint">audit</span></h2>
    <div id="a11y-host" class="a11y"></div>
  </section>

  <!-- TODO: add remaining spec sections: Motion+gestures · Deep-link map · Pixel spec · Interaction matrix · Widget-tree + navigation mapping. See examples/shop-flow.html. -->

  <div class="foot"><span><!-- TODO: footer --></span></div>
</main>

<!-- Framework JS — order matters -->
<script src="_framework/icons.js"></script>
<script src="_framework/gestures.js"></script>
<script src="_framework/state-swap.js"></script>
<script src="_framework/device-selector.js"></script>
<script src="_framework/theme-selector.js"></script>
<script src="_framework/router.js"></script>
<script src="_framework/flowmap.js"></script>
<script src="_framework/a11y.js"></script>

<script>
/* TODO: seed data */
const seed = () => ({ items: [], loading: false, dark: false });
var state = seed();   /* var (not let) so the router can read it as a window global */

function statusBar() { return `<div class="status-bar"><span>9:41</span><span class="icons">${I.signal}${I.wifi}${I.battery}</span></div>`; }

/* TODO: register one screen per node. ctx = {surface,theme,state,back,navigate}. */
Router.registerScreen('home', {
  title: 'Home', tab: 'home', links: ['detail'],
  render: (ctx) => `<div class="appbar"><div class="appbar-title"><h2>Home</h2></div></div>
    <div class="list pad">${(ctx.state.items||[]).map(it => `
      <div class="digrow" data-id="${it.id}" onpointerdown="gStart(event, ${it.id})">${it.title}</div>`).join('')}</div>`,
});
Router.registerScreen('detail', {
  title: 'Detail', links: ['home'],
  render: (ctx) => `<div class="appbar"><button class="navbar-back" onclick="Router.back()">${I.back} Back</button></div>
    <div class="pad"><h2>Detail</h2></div>`,
});

/* gesture globals */
function tapRow(id) { Router.navigate('detail', { mode: 'push' }); }
function deleteItem(id) { state.items = state.items.filter(i => i.id !== id); /* re-render current screen */ Router.navigate(Router.current().id, { mode: 'replace' }); }

function toggleDark() {
  state.dark = !state.dark;
  document.querySelectorAll('.phone-screen').forEach(s => s.classList.toggle('dark', state.dark));
  document.body.classList.toggle('dark-tokens', state.dark);
  const b = document.getElementById('dark-btn'); b.classList.toggle('on', state.dark); b.textContent = state.dark ? 'Light mode' : 'Dark mode';
}

/* catalog: render a named screen with temp state (note 2 params → per-screen) */
function catalogScreen(stateName, screenId) {
  return withTempState(temp => {
    switch (stateName) { case 'loading': temp.loading = true; break; case 'empty': temp.items = []; break; }
  }, () => {
    const scr = Router.getScreens()[screenId] || Router.current();
    return statusBar() + scr.render({ surface: document.body.dataset.surface, theme: 'neutral', state: state, back(){}, navigate(){} });
  });
}

/* Mount */
document.getElementById('theme-selector-host').innerHTML = ThemeKit.renderThemeSelector();
document.getElementById('device-selector-host').innerHTML = renderDeviceSelector();
ThemeKit.mountThemeSelector('neutral');
mountDeviceSelector('iphone-17-pro-max');
Router.mountTabBar([{ id: 'home', label: 'Home', icon: I.home, screen: 'home' }]);
Router.mount('screen', 'home');
Flowmap.mount('flowmap-host');
A11y.mountAudit('a11y-host');
mountCatalog(catalogScreen);
window.addEventListener('devicechange', () => Router.navigate(Router.current().id, { mode: 'replace' }));
window.addEventListener('themechange', e => { const o = ThemeKit.THEMES.find(t => t.id === e.detail.id); document.getElementById('qr-theme').textContent = o ? o.name : e.detail.id; });
</script>
</body>
</html>
```

- [ ] **Step 4: Build `examples/shop-flow.html`** — copy the template, then author a full-fat shop flow that exercises every feature. Requirements (the acceptance grep in Step 1 enforces the headline ones):
  - **≥ 3 `registerScreen` calls:** `catalog` (tab `shop`, grid of ≥4 products with real Unsplash images `https://images.unsplash.com/...?w=200&h=200&fit=crop&q=80`, each links to `product`), `product` (push; "Add to cart" → updates `state.cart`, links to `cart`), `cart` (tab `cart`; lists items, "Checkout" → modal, links to `checkout`), `checkout` (modal; order summary).
  - **Tab bar:** `Router.mountTabBar([{id:'shop',…,screen:'catalog'},{id:'cart',…,screen:'cart'}])`.
  - **States** in `catalogScreen`: `default`, `loading` (skeleton), `empty` (empty cart), `error`; catalog tiles for each meaningful (screen,state) pair using `data-screen`.
  - **Theme switcher + device selector** mounted (from the template).
  - **A11y section** via `A11y.mountAudit('a11y-host')`.
  - **Full spec sections** authored: Motion+gestures (incl. push/pop/modal curves+durations), Deep-link map (→ screens), Pixel spec (active theme name), Interaction matrix (every tappable → feedback/state/API/target-screen/analytics/error), Widget-tree + navigation mapping (Flutter `Navigator`/SwiftUI `NavigationStack`/Compose `NavHost`).
  - Replace all TODO markers; no `TODO` left in the example.

- [ ] **Step 5: Run to verify pass** — `bash scripts/app-mocks.test.sh` → Task 10 `ok` (note: `a11y.js` is created in Task 11; if running before Task 11, the template's `<script src=a11y.js>` is fine — the grep only checks the tag exists. The `A11y.mountAudit` call will no-op until Task 11. Re-run after Task 11.)

- [ ] **Step 6: Commit**

```bash
git add skills/app-interactive-mocks/template.html skills/app-interactive-mocks/examples/shop-flow.html scripts/app-mocks.test.sh
git commit -m "feat: flow-aware template + full-fat shop-flow example"
```

---

## Task 11: `a11y.js` (new — accessibility audit)

**Files:**
- Create: `skills/app-interactive-mocks/framework/a11y.js`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions (pure contrast math)**

```bash
# ---- Task 11: a11y ----
node --check "$FW/a11y.js" >/dev/null 2>&1 && echo "ok   - a11y.js parses" || { echo "FAIL - a11y.js syntax"; fails=$((fails+1)); }
check "contrast black/white = 21" "21" "$(jeval "const A=require('$FW/a11y.js'); console.log(Math.round(A.contrastRatio('#000000','#ffffff')))")"
check "wcag 21 is AAA"   "AAA"  "$(jeval "const A=require('$FW/a11y.js'); console.log(A.wcagLevel(A.contrastRatio('#000000','#ffffff'),{large:false}))")"
check "wcag low is fail" "fail" "$(jeval "const A=require('$FW/a11y.js'); console.log(A.wcagLevel(A.contrastRatio('#999999','#ffffff'),{large:false}))")"
check "exposes mountAudit" "mountAudit" "$(cat "$FW/a11y.js" 2>/dev/null)"
```

- [ ] **Step 2: Run to verify failure** — `bash scripts/app-mocks.test.sh` → Task 11 FAIL.

- [ ] **Step 3: Write `a11y.js`**

```js
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
```
(The `TODO (author)` inside the generated a11y section is intentional output for the human author of a *specific* mock to fill — it is not a plan placeholder.)

- [ ] **Step 4: Run to verify pass** — `bash scripts/app-mocks.test.sh` → Task 11 `ok` AND the Task 10 a11y line now meaningful; `0 failure(s)`.

- [ ] **Step 5: Commit**

```bash
git add skills/app-interactive-mocks/framework/a11y.js scripts/app-mocks.test.sh
git commit -m "feat: accessibility audit (contrast + tap targets + semantics scaffold)"
```

---

## Task 12: `SKILL.md`

**Files:**
- Create: `skills/app-interactive-mocks/SKILL.md`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions**

```bash
# ---- Task 12: SKILL.md ----
check "SKILL has frontmatter name" "name: app-interactive-mocks" "$(cat "$SKILL/SKILL.md" 2>/dev/null)"
check "SKILL description mentions interactive prototype" "interactive prototype" "$(cat "$SKILL/SKILL.md" 2>/dev/null)"
check "SKILL covers web/tablet"   "tablet" "$(cat "$SKILL/SKILL.md" 2>/dev/null)"
check "SKILL documents first-time setup" "design/_framework" "$(cat "$SKILL/SKILL.md" 2>/dev/null)"
[ "$(head -1 "$SKILL/SKILL.md" 2>/dev/null)" = "---" ] && echo "ok   - SKILL starts with frontmatter" || { echo "FAIL - SKILL frontmatter"; fails=$((fails+1)); }
```

- [ ] **Step 2: Run to verify failure** — `bash scripts/app-mocks.test.sh` → Task 12 FAIL.

- [ ] **Step 3: Write `SKILL.md`** (adapt the source SKILL.md; generalize triggers; document the new workflow)

````markdown
---
name: app-interactive-mocks
description: Use when the user asks for high-fidelity interactive app mocks, a clickable/walkable prototype, a multi-screen design flow, a "Figma-quality" mockup, or an execution-ready design spec for a mobile, tablet, or web app. Generates one self-contained HTML file per flow: an interactive multi-screen playground (in-frame router, back-stack, tab bars, real gestures, push/pop/modal transitions) across phone/tablet/foldable/web device frames, a 20+ theme gallery with live switching, a drift-proof state catalog, light+dark themes, an accessibility audit (contrast, tap targets, dynamic type, semantics, focus order), and execution-ready spec sections (motion, deep-links, pixel spec, interaction matrix, widget-tree + navigation mapping to Flutter/SwiftUI/Compose). Trigger phrases: "design mocks", "interactive/clickable prototype", "high-fi mockup", "walkable flow", "spec for the dev", "build me an inbox/profile/settings/checkout screen or flow". Use BEFORE writing native/Flutter/web UI code for a new screen or flow.
---

# app-interactive-mocks

Build production-grade, **walkable** app mocks as a single HTML file per flow — good enough that a Flutter / SwiftUI / Jetpack Compose / web dev implements directly from it. No Figma.

## When to invoke / not invoke
- Invoke: "design mocks", "interactive/clickable prototype", "high-fi mockup", "walkable flow", "spec for the dev", a new screen or multi-screen flow on mobile/tablet/web.
- Don't: quick wireframes (talk it through), backend/API design, pure copy edits.

## What it produces
One file at `design/<flow>.html`: hero+quickref · control strip (surface/device selector · 20+ theme switcher · dark toggle · flow-map toggle) · interactive multi-screen playground · auto-derived flow map · drift-proof state catalog · light+dark pair · spec sections (motion+gestures incl. transitions · accessibility audit · deep-link map · pixel spec · interaction matrix · widget-tree + navigation mapping).

## Workflow
1. **First-time setup** (skip if `design/_framework/` exists):
   ```bash
   mkdir -p design/_framework
   cp "${CLAUDE_PLUGIN_ROOT}/skills/app-interactive-mocks/framework/"* design/_framework/
   ```
   Pick a theme from the gallery, or auto-detect tokens from `theme.dart` / `tailwind.config.(js|ts)` / `tokens.json` / `:root` and write them into `design/_framework/tokens.css`. Otherwise the neutral default applies.
2. **Per-flow scaffold:** `cp "${CLAUDE_PLUGIN_ROOT}/skills/app-interactive-mocks/template.html" design/<flow>.html`.
3. **Iterate, playground first.** Register one screen per node (`Router.registerScreen`), wire links + tabs, show the rendered file after every change (`open design/<flow>.html` or drive the `file://` URL with a browser tool). Flip surfaces and themes to verify.
4. **Lock the spec** in order: state catalog → light/dark pair → motion+gestures (incl. transitions) → accessibility audit → deep-link map → pixel spec → interaction matrix → widget-tree + navigation mapping.

## Framework files (in `framework/`, copied to `design/_framework/`)
`tokens.css` (neutral defaults + overrides) · `themes.css` (20+ presets) · `theme-selector.js` · `frame.css` (phone/tablet/foldable/web) · `device-selector.js` · `components.css` · `spec-styles.css` · `router.js` (in-frame router) · `flowmap.js` (auto-derived graph) · `a11y.js` (audit) · `state-swap.js` (drift-proof catalog) · `gestures.js` · `icons.js`.

## Quality bar
iPhone 17 Pro Max default (440×956 pt), verified at 375 pt + a tablet + a web breakpoint · values in pt/dp · catalog via state-swap (no drift) · flow map auto-derived (no hand-maintained graph) · interaction matrix covers every tappable (feedback/state/API/target-screen/analytics/error) · widget-tree names a specific widget+package · real images (Unsplash `?w=200&h=200&fit=crop&q=80`) · tokens never hard-coded.

## Anti-patterns
Static-only HTML · catalog/playground drift · one-device-only · hover-revealed actions · long-press for primary actions · hard-coded tokens · multi-file flows · skipping the interaction matrix or a11y section.

## Reference
`examples/shop-flow.html` — full-fat catalog → product → cart → checkout flow exercising router, tabs, surfaces, theme switching, states, and every spec section.
````

- [ ] **Step 4: Run to verify pass** — `bash scripts/app-mocks.test.sh` → Task 12 `ok`.

- [ ] **Step 5: Commit**

```bash
git add skills/app-interactive-mocks/SKILL.md scripts/app-mocks.test.sh
git commit -m "feat: SKILL.md for app-interactive-mocks (triggers + workflow)"
```

---

## Task 13: Skill `README.md` + discoverability (repo README + plugin.json)

**Files:**
- Create: `skills/app-interactive-mocks/README.md`
- Modify: `README.md` (repo root)
- Modify: `.claude-plugin/plugin.json`
- Modify: `scripts/app-mocks.test.sh`

- [ ] **Step 1: Append failing assertions**

```bash
# ---- Task 13: docs + discoverability ----
check "skill README exists" "app-interactive-mocks" "$(cat "$SKILL/README.md" 2>/dev/null)"
check "repo README mentions the skill" "app-interactive-mocks" "$(cat "$ROOT/README.md" 2>/dev/null)"
check "plugin.json mentions mocks" "mock" "$(cat "$ROOT/.claude-plugin/plugin.json" 2>/dev/null)"
jeval "JSON.parse(require('fs').readFileSync('$ROOT/.claude-plugin/plugin.json','utf8')); console.log('PLUGIN_JSON_OK')" | grep -q PLUGIN_JSON_OK && echo "ok   - plugin.json valid" || { echo "FAIL - plugin.json invalid JSON"; fails=$((fails+1)); }
```

- [ ] **Step 2: Run to verify failure** — `bash scripts/app-mocks.test.sh` → Task 13 FAIL.

- [ ] **Step 3a: Write `skills/app-interactive-mocks/README.md`** — a user-facing summary (adapt the source README.md): what it produces, the file list, the quick workflow, the theme gallery, surfaces, and the a11y section. Keep it project-agnostic (no Aadhaa references).

- [ ] **Step 3b: Edit `.claude-plugin/plugin.json`** — broaden `description` and add keywords. Replace the `description` value with:
```
"Team-dev workflow with selectable evaluation tiers, PLUS app-interactive-mocks — generate walkable, multi-surface, Figma-quality interactive UI mocks as a single HTML file per flow."
```
And add to the `keywords` array: `"design", "mocks", "prototype", "ui", "figma"`.

- [ ] **Step 3c: Edit the repo `README.md`** — add a section after "Usage":
```markdown
## Design mocks — `app-interactive-mocks`

Bundled skill: generate **walkable, multi-screen, Figma-quality** interactive UI mocks (phone/tablet/foldable/web) as one self-contained HTML file per flow — with a 20+ theme gallery, drift-proof state catalog, accessibility audit, and execution-ready spec sections (interaction matrix, widget-tree + navigation mapping).

```bash
/consortium:app-interactive-mocks            # or just ask: "design mocks for a checkout flow"
```

See `skills/app-interactive-mocks/README.md`.
```

- [ ] **Step 4: Run to verify pass** — `bash scripts/app-mocks.test.sh` → Task 13 `ok`; `0 failure(s)`.

- [ ] **Step 5: Commit**

```bash
git add skills/app-interactive-mocks/README.md README.md .claude-plugin/plugin.json scripts/app-mocks.test.sh
git commit -m "docs: app-interactive-mocks README + plugin discoverability"
```

---

## Task 14: Full-suite green + browser verification

**Files:** none (verification only).

- [ ] **Step 1: Run the complete automated suite**

Run: `bash scripts/app-mocks.test.sh`
Expected: every line `ok`; final `0 failure(s)`; exit 0.

- [ ] **Step 2: Syntax-check every framework JS once more**

Run: `for f in skills/app-interactive-mocks/framework/*.js; do node --check "$f" && echo "ok $f"; done`
Expected: `ok` for all 8 JS files; no syntax errors.

- [ ] **Step 3: Browser verification of the example** (Claude drives the Playwright / chrome-devtools MCP against the `file://` URL `skills/app-interactive-mocks/examples/shop-flow.html`). Confirm each:
  - Playground renders the `catalog` screen with product images.
  - Tap a product → pushes `product` (transition plays); Back → pops to `catalog`.
  - Tab bar switches `shop` ↔ `cart`; "Checkout" opens `checkout` as a modal.
  - Device selector switches phone → iPad → foldable (crease shows) → web (browser chrome shows); layout holds at 375 pt too.
  - Theme switcher changes the palette live; the a11y **contrast table recomputes** on switch.
  - Dark toggle flips light/dark.
  - Flow map shows nodes + edges; clicking a node jumps screens; current node highlighted.
  - Catalog tiles match the playground for each state (no drift).
  - With OS "reduce motion" on, transitions are suppressed (verify via `prefers-reduced-motion` emulation).

- [ ] **Step 4: Fix anything surfaced, re-run Steps 1–3, then commit fixes** (skip if none)

```bash
git add -A && git commit -m "fix: address app-interactive-mocks verification findings"
```

- [ ] **Step 5: Manual install-and-exercise** (run by the user in an interactive Claude Code session)
  - `/plugin marketplace add /Users/nagarjuna/projects/consortium` then `/plugin install consortium@consortium` (or update if already installed).
  - Confirm `/consortium:app-interactive-mocks` appears and invokes the skill.
  - In a scratch project: ask "design mocks for a 2-screen settings flow" → confirm the skill copies `_framework/`, scaffolds `design/…html`, and the file opens as a walkable mock.

---

## Self-Review (completed during planning)

**1. Spec coverage:**
- §5.2 framework inventory (13 files) → Tasks 2–11 create all 13; load order fixed in the Contracts block + Task 10 template.
- §5.3 theming (neutral default, 20+ gallery light+dark, live switch, precedence) → Tasks 2 (neutral), 3 (gallery + selector). Auto-detect precedence is documented in SKILL.md (Task 12) as authoring guidance (it is per-project work the skill performs at use time, not a framework file).
- §6 generated-file anatomy → Task 10 template + Task 10 example realize every section; a11y section → Task 11.
- §7.1 router + flow map → Tasks 8, 9. §7.2 surfaces → Task 4. §7.3 a11y → Task 11.
- §9 distribution (layout, SKILL triggers, no command, manifest touch-ups, generic example) → Tasks 10, 12, 13.
- §10 quality bar / anti-patterns → encoded in SKILL.md (Task 12) + verified in Task 14.
- §11 verification plan → Task 14 Steps 3 & 5.

**2. Placeholder scan:** The only `TODO` strings that remain in deliverables are (a) the template's authoring markers (intended — they guide the human filling a specific mock) and (b) the a11y section's "TODO (author)" semantics row (intended output). The *example* (`shop-flow.html`) must have **no** TODOs (enforced by Task 10 acceptance). No plan step defers implementation. The 23-theme expansion is driven by a complete seed table (actual hex values), not a placeholder, and is cross-checked by the Task 3 node assertion that every `THEMES` id has a CSS block.

**3. Type/name consistency:** Verified against the Contracts block — `Router.{registerScreen,navigate,back,current,stack,getScreens,mountTabBar,mount,_reduce}`, `Flowmap.{deriveGraph,mount}`, `A11y.{hexToRgb,relLuminance,contrastRatio,wcagLevel,auditTapTargets,mountAudit}`, `ThemeKit.{THEMES,applyTheme,renderThemeSelector,mountThemeSelector}` are used identically in their modules, the template (Task 10), and the tests. Preserved globals (`gStart`, `withTempState`/`mountCatalog`/`mountThemePair`, `applyDevice`/`renderDeviceSelector`/`mountDeviceSelector`, `I`, `state`/`render`/`statusBar`) keep the source signatures. `data-theme` is set on `document.documentElement` everywhere; `data-surface` on `document.body` everywhere.

**4. Sequencing note:** Task 10 (template/example) references `a11y.js`, created in Task 11. This is deliberate (template authored as one unit); the Task 10 grep only checks the `<script>` tag, and Task 11's step 4 re-runs the suite so the a11y wiring is exercised after `a11y.js` exists. If executing strictly in order, treat Task 10 step 5 as "tag present" and Task 14 as the binding behavioral gate.
````
