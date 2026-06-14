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

13 files copied to `design/_framework/`:

`tokens.css` · `themes.css` · `theme-selector.js` · `frame.css` · `device-selector.js` · `components.css` · `spec-styles.css` · `router.js` · `flowmap.js` · `a11y.js` · `state-swap.js` · `gestures.js` · `icons.js`

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

**Iterate, playground first.** Register screens with `Router.registerScreen`, wire links and tabs, then open the file in a browser after each change:

```bash
open design/<flow>.html     # macOS
# or drive the file:// URL with a browser/Playwright tool
```

Flip surfaces and themes to verify. Lock the spec sections once the playground is stable.

## Themes

20+ presets in `themes.css` — Material You, iOS, Fluent, Pastel, AMOLED, High-contrast, and more. Live-switch via the control strip. Override `design/_framework/tokens.css` to apply project-specific brand tokens; everything in the playground and spec derives from those tokens automatically.

## Surfaces

`frame.css` + `device-selector.js` support four surfaces:

| Surface | Examples |
|---|---|
| `phone` | iPhone 17 Pro Max (440×956 pt default), Pixel 9 Pro, Galaxy S25 |
| `tablet` | iPad Pro 13″, Galaxy Tab S10 Ultra, Pixel Tablet |
| `foldable` | Galaxy Z Fold 6 (cover + unfolded), Pixel 9 Pro Fold |
| `web` | 1280 px desktop breakpoint |

Switch surfaces in the control strip; the frame and layout adapt automatically.

## Accessibility

`a11y.js` runs a live audit panel covering:

- **Contrast** — WCAG 2.1 AA/AAA ratio check for all text/background pairs
- **Tap targets** — flags elements smaller than 44×44 pt
- **Dynamic type** — verifies text scales with token-based font sizes
- **Semantics** — checks for `aria-label` / `role` on interactive elements
- **Focus order** — traces keyboard/focus traversal path

## Example

`examples/shop-flow.html` — a full catalog → product → cart → checkout flow demonstrating the router, tab bars, all four surfaces, theme switching, complete state catalog, and every spec section.
