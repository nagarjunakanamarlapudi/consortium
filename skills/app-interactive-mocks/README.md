# app-interactive-mocks

Generate **walkable, multi-screen, Figma-quality** interactive UI mocks as one self-contained HTML file per flow — phone, tablet, foldable, and web — ready for Flutter / SwiftUI / Jetpack Compose / web implementation.

## What it produces

One file at `design/<flow>.html` containing:

- **Hero + quickref** — flow title, surface/device selector, theme switcher, dark toggle, flow-map toggle
- **Interactive playground** — multi-screen in-frame router with push/pop/modal/tab transitions, real gestures, back-stack
- **Auto-derived flow map** — graph of all screens and navigation edges, no manual maintenance
- **Drift-proof state catalog** — every screen state (loading, empty, error, populated) via `state-swap.js`
- **Light + dark pair** — live toggle, token-driven, no hard-coded colours
- **Spec sections** — motion + gestures · accessibility audit (contrast, tap targets, dynamic type, semantics, focus order) · deep-link map · pixel spec · interaction matrix · widget-tree + navigation mapping

## Framework files

14 files copied to `design/_framework/`:

`tokens.css` · `themes.css` · `theme-selector.js` · `frame.css` · `device-selector.js` · `components.css` · `spec-styles.css` · `router.js` · `flowmap.js` · `a11y.js` · `state-swap.js` · `gestures.js` · `icons.js` · `bundle.mjs`

## Quick workflow

**First-time setup** (skip if `design/_framework/` already exists):

```bash
mkdir -p design/_framework
cp "${CLAUDE_PLUGIN_ROOT}/skills/app-interactive-mocks/framework/"* design/_framework/
```

Optionally auto-detect tokens from `theme.dart`, `tailwind.config.(js|ts)`, `tokens.json`, or `:root` CSS and write them into `design/_framework/tokens.css`. Otherwise the neutral default applies.

**Per-flow scaffold:**

```bash
cp "${CLAUDE_PLUGIN_ROOT}/skills/app-interactive-mocks/template.html" design/<flow>.html
```

**Iterate, playground first.** Register screens with `Router.registerScreen`, wire links and tabs, then re-check the render after each change. **Serve over a local server — don't use `file://`:**

```bash
python3 -m http.server -d design 8753
# then open / screenshot http://localhost:8753/<flow>.html
```

Why not `file://`? A page opened directly from disk is sandboxed by browsers (and by the Playwright/Chrome MCP tools) from loading the external `_framework/*` files, so it renders unstyled with no JavaScript. Flip surfaces and themes to verify. Lock the spec sections once the playground is stable.

**Bundle for delivery.** The authored `design/<flow>.html` references the external `_framework/*` files, so it only renders over http and looks broken on a `file://` double-click. Produce the portable, self-contained artifact:

```bash
node design/_framework/bundle.mjs design/<flow>.html
# -> design/<flow>.standalone.html  (all CSS/JS inlined; CDN fonts kept)
```

Hand off the `.standalone.html`: it opens by double-click, shares as a single file, and works offline.

## Themes

24 presets in `themes.css` — branded hues (Indigo, Teal, Emerald, Rose, Amber, Violet, Sky, Orange, Crimson, Cyan, Lime, Fuchsia, Slate) plus named aesthetics (Material You, iOS, Nord, Dracula, Solarized, Catppuccin, Tokyo Night, Rosé Pine, Gruvbox, One Dark), each with light + dark variants. Live-switch via the control strip. Override `design/_framework/tokens.css` to apply project-specific brand tokens; everything in the playground and spec derives from those tokens automatically.

## Surfaces

`frame.css` + `device-selector.js` support four surfaces:

| Surface | Examples |
|---|---|
| `phone` | iPhone 17 Pro Max (440×956 pt default) → SE, Pixel 9 Pro/9, Galaxy S25 Ultra/S25 |
| `tablet` | iPad Pro 13″, iPad Pro 11″, iPad mini |
| `foldable` | Galaxy Z Fold (open + cover), Pixel Fold (open + cover) |
| `web` | 390 / 768 / 1280 / 1440 px breakpoints |

Switch surfaces in the control strip; the frame and layout adapt automatically.

## Accessibility

`a11y.js` runs a live audit panel covering:

- **Contrast** — WCAG 2.2 AA/AAA ratio check for the active theme's key text/background pairs (auto-computed; recomputes on theme switch)
- **Tap targets** — flags rendered interactive elements smaller than 44×44 pt (auto-computed)
- **Semantics, focus order & dynamic type** — a guided checklist to complete per mock (role/label/hint, traversal order, text-scale behaviour, reduced-motion fallback)

## Example

`examples/shop-flow.html` — a full catalog → product → cart → checkout flow demonstrating the router, tab bars, all four surfaces, theme switching, complete state catalog, and every spec section.
