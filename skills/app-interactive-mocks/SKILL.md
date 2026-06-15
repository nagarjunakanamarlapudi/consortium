---
name: app-interactive-mocks
description: Use when the user asks for high-fidelity interactive app mocks, a clickable/walkable interactive prototype, a multi-screen design flow, a "Figma-quality" mockup, or an execution-ready design spec for a mobile, tablet, or web app. Generates one self-contained HTML file per flow: an interactive multi-screen playground (in-frame router, back-stack, tab bars, real gestures, push/pop/modal transitions) across phone/tablet/foldable/web device frames, a 20+ theme gallery with live switching, a drift-proof state catalog, light+dark themes, an accessibility audit (contrast, tap targets, dynamic type, semantics, focus order), and execution-ready spec sections (motion, deep-links, pixel spec, interaction matrix, widget-tree + navigation mapping to Flutter/SwiftUI/Compose). Trigger phrases: "design mocks", "interactive/clickable prototype", "high-fi mockup", "walkable flow", "spec for the dev", "build me an inbox/profile/settings/checkout screen or flow". Use BEFORE writing native/Flutter/web UI code for a new screen or flow.
---

# app-interactive-mocks

Build production-grade, **walkable** app mocks as a single HTML file per flow — good enough that a Flutter / SwiftUI / Jetpack Compose / web dev implements directly from it. No Figma.

## When to invoke / not invoke
- Invoke: "design mocks", "interactive/clickable prototype", "high-fi mockup", "walkable flow", "spec for the dev", a new screen or multi-screen flow on mobile/tablet/web.
- Don't: quick wireframes (talk it through), backend/API design, pure copy edits.

## What it produces
One file at `design/<flow>.html`: hero+quickref · control strip (surface/device selector · 20+ theme switcher · dark toggle · flow-map toggle) · interactive multi-screen playground · auto-derived flow map · drift-proof state catalog · light+dark pair · spec sections (motion+gestures incl. transitions · accessibility audit · deep-link map · pixel spec · interaction matrix · widget-tree + navigation mapping). The shippable deliverable is the bundled `design/<flow>.standalone.html` — one self-contained file that opens by double-click (see Workflow 5).

## Workflow
1. **First-time setup** (skip if `design/_framework/` exists):
   ```bash
   mkdir -p design/_framework
   cp "${CLAUDE_PLUGIN_ROOT}/skills/app-interactive-mocks/framework/"* design/_framework/
   ```
   Pick a theme from the gallery, or auto-detect tokens from `theme.dart` / `tailwind.config.(js|ts)` / `tokens.json` / `:root` and write them into `design/_framework/tokens.css`. Otherwise the neutral default applies.
2. **Per-flow scaffold:** `cp "${CLAUDE_PLUGIN_ROOT}/skills/app-interactive-mocks/template.html" design/<flow>.html`.
3. **Iterate, playground first.** Register one screen per node (`Router.registerScreen`), wire links + tabs, and re-check the render after every change. **Verify over a local server, not `file://`:** `python3 -m http.server -d design 8753`, then open / screenshot `http://localhost:8753/<flow>.html`. A `file://` page cannot load the external `_framework/*` files — browsers (and the Playwright/Chrome MCP tools) block it — so it renders unstyled with no JS. Flip surfaces and themes to verify.
4. **Lock the spec** in order: state catalog → light/dark pair → motion+gestures (incl. transitions) → accessibility audit → deep-link map → pixel spec → interaction matrix → widget-tree + navigation mapping.
5. **Bundle for delivery.** The authored `design/<flow>.html` links external `_framework/*` files, so it only renders over http — it appears broken on `file://` double-click. Produce the portable artifact: `node design/_framework/bundle.mjs design/<flow>.html` → writes `design/<flow>.standalone.html` (all CSS/JS inlined; CDN fonts kept). Hand the user the `.standalone.html` — it opens by double-click, shares as one file, and works offline.

## Framework files (in `framework/`, copied to `design/_framework/`)
`tokens.css` (neutral defaults + overrides) · `themes.css` (20+ presets) · `theme-selector.js` · `frame.css` (phone/tablet/foldable/web) · `device-selector.js` · `components.css` · `spec-styles.css` · `router.js` (in-frame router) · `flowmap.js` (auto-derived graph) · `a11y.js` (audit) · `state-swap.js` (drift-proof catalog) · `gestures.js` · `icons.js` · `bundle.mjs` (inline → self-contained `.standalone.html` deliverable).

## Quality bar
iPhone 17 Pro Max default (440×956 pt), verified at 375 pt + a tablet + a web breakpoint · values in pt/dp · catalog via state-swap (no drift) · flow map auto-derived (no hand-maintained graph) · interaction matrix covers every tappable (feedback/state/API/target-screen/analytics/error) · widget-tree names a specific widget+package · real images (Unsplash `?w=200&h=200&fit=crop&q=80`) · tokens never hard-coded.

## Anti-patterns
Static-only HTML · catalog/playground drift · one-device-only · hover-revealed actions · long-press for primary actions · hard-coded tokens · skipping the interaction matrix or a11y section · verifying via `file://` (renders unstyled — serve over http) · shipping the link-based `design/<flow>.html` as the deliverable instead of the bundled `.standalone.html` (breaks on double-click).

## Reference
`examples/shop-flow.html` — full-fat catalog → product → cart → checkout flow exercising router, tabs, surfaces, theme switching, states, and every spec section.
