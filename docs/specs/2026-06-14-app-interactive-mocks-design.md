# App Interactive Mocks — Design Spec

- **Date:** 2026-06-14
- **Status:** Approved (brainstorm complete) → ready for implementation plan
- **Author:** Nagarjuna (with Claude)
- **Skill name:** `app-interactive-mocks`
- **Ships in:** the `consortium` plugin (`consortium/skills/app-interactive-mocks/`)

---

## 1. Summary

A distributable Claude Code skill that generates **one self-contained HTML file per feature _flow_** — a high-fidelity, **walkable, multi-screen** interactive prototype with a drift-proof state catalog, a **20+ theme gallery** with live switching, **multi-surface device frames** (phone / tablet / foldable / web), an **accessibility audit**, light + dark themes, and execution-ready spec sections (motion, deep-links, pixel spec, interaction matrix, and widget-tree **+ navigation** mapping to Flutter / SwiftUI / Compose).

It is a generalized, project-agnostic evolution of the Aadhaa `mobile-app-mocks` skill, packaged so other teams can install it via the consortium plugin. The artifact is good enough that a developer implements directly from it — **no Figma required**.

## 2. Goals / Non-goals

**Goals**
- Generalize the Aadhaa `mobile-app-mocks` skill into a **project-agnostic, distributable** skill.
- Add four richer capabilities on top of the original single-screen mock:
  1. **Multi-screen clickable flows** (walkable prototype).
  2. **More surfaces** — tablet, foldable, responsive web (beyond the existing 9 phones).
  3. **Accessibility audit** section.
  4. **20+ theme gallery** with a live in-playground switcher.
- Preserve the original's core strengths: **single-file portability**, **drift-proof state catalog**, and **execution-ready spec depth**.

**Non-goals (YAGNI / deferred)**
- **Real code export / scaffolding** — explicitly out of scope. The dev-handoff bridge stays the *widget-tree mapping* table. (Deferred; see §12.)
- **Standalone plugin or separate repo** — it lives inside consortium.
- **Backend / API mocking**, data modeling, or business logic.
- **A dedicated slash command** — skills are slash-invocable; see §4 / §9.

## 3. Context

**Source — Aadhaa `mobile-app-mocks`** (`~/projects/Aadhaa/.claude/skills/mobile-app-mocks`):
single-screen, phone-only, with Aadhaa-specific defaults (teal/amber, Outfit + Inter). Structure today:
`SKILL.md`, `README.md`, `template.html`, `framework/{tokens,devices,phone-frame,components,spec-styles}.css` + `{icons,gestures,state-swap,device-selector}.js`, `examples/notifications-inbox.html` (~1,700 LOC, self-contained, pre-dates framework extraction).

**Target — `consortium` plugin** (`~/projects/consortium`): a published Claude Code plugin + marketplace, currently themed around team-dev evaluation tiers. Skills are auto-discovered under `skills/`, so adding a directory ships it with the plugin (no structural manifest change required). Adding this skill broadens the plugin's scope from "review/eval" to "review/eval **+ design mocks**".

## 4. Key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Packaging | Skill **inside** the consortium plugin | Simplest distribution; reuses the existing published plugin. |
| Name | `app-interactive-mocks` | Broad (mobile+tablet+web); foregrounds interactivity. |
| Multi-screen architecture | **Option A** — single self-contained HTML per flow, with an in-frame **router** + auto-derived **flow map** | Preserves single-artifact portability; flow map doubles as nav docs. Multi-file (Option B) rejected — fragments the spec, breaks the single-artifact strength. |
| Theming | Neutral default **+ 20+ preset gallery** (light+dark) **+ live switcher**; precedence: explicit pick → auto-detected project tokens → neutral | Instant variety for exploration; zero-config start; respects real project tokens when present. |
| Discoverability | Rely on **skill auto-trigger** + slash invocation `/consortium:app-interactive-mocks`; **no dedicated command** | Installed skills are slash-invocable on recent Claude Code; a command would only add a shorter alias. A thin alias can be added later if wanted. |
| Tap-target audit | **Folds into** the new Accessibility section | It belongs there; avoids duplication. |
| Relationship to original | Fresh **generalized port**; Aadhaa original left untouched | No coupling/regression risk to Aadhaa. |

## 5. Architecture

### 5.1 Output model

One HTML file per flow at `design/<flow-name>.html`, importing shared assets from `design/_framework/`. **No build step**; opens in any browser. A *flow* = a set of related screens (e.g. an inbox → thread → settings flow).

### 5.2 Framework inventory (final)

Copied once into `design/_framework/` on first use; never regenerated per feature.

| File | Responsibility | vs. original |
|---|---|---|
| `tokens.css` | Base CSS variables + **neutral** default values + documented `:root` override block | De-Aadhaa'd |
| `themes.css` | **20+ theme presets** as `[data-theme="…"]` selectors, each with light + dark values | **New** |
| `theme-selector.js` | Live theme dropdown; sets `data-theme`, persists choice, triggers a11y recompute | **New** |
| `frame.css` | **Surface-aware device frame** keyed on `data-surface` (`phone`/`tablet`/`foldable`/`web`) + `--device-*` vars | Merges `phone-frame.css` + `devices.css`, generalized |
| `device-selector.js` | Device registry **grouped by surface** + dropdown + `applyDevice` | Extended |
| `components.css` | Cross-surface primitives: rows, cards, sheets, pills, toasts, **app/nav bar, tab bar, web top-nav** | Extended |
| `spec-styles.css` | Page chrome (hero, quickref, tables, catalog grid) + **flow-map** + **a11y** styling | Extended |
| `router.js` | In-frame screen router: `navigate`/`push`/`replace`/`pop`, back-stack, tab host, transitions | **New** |
| `flowmap.js` | Auto-derived screen graph (nodes from screens, edges from declared `links`); click to jump | **New** |
| `a11y.js` | Computes contrast, tap-target sizes, dynamic-type re-renders; emits the a11y section | **New** |
| `state-swap.js` | Drift-proof catalog tile renderer (state-mutation pattern) | Kept |
| `gestures.js` | Pointer-event tap / swipe (+ optional long-press / drag) | Lightly extended |
| `icons.js` | SVG icon library (status bar + common UI) | Kept |

Plus, at the skill root: `SKILL.md`, `README.md`, `template.html`, `examples/<generic-flow>.html`.

### 5.3 Theming & genericization

- **Neutral default** theme (indigo primary, slate neutrals, Inter / system fonts) so the skill works zero-config.
- **20+ presets** in `themes.css`, each shipping a **light and dark** variant, applied via `data-theme` on the root and switched live in the playground. Curated mix:
  - *Branded hues:* Indigo, Teal, Emerald, Rose, Amber, Violet, Sky, Orange, Crimson, Cyan, Lime, Fuchsia, Slate (monochrome).
  - *Named aesthetics:* Material You, iOS System, Nord, Dracula, Solarized, Catppuccin (Latte/Mocha), Tokyo Night, Rosé Pine, Gruvbox, One Dark.
  - (≥ 23 total; final list locked during implementation.)
- Each theme defines the same token contract: `--primary`, `--primary-600`, `--primary-soft`, `--accent`, `--bg`, `--surface`, `--surface-2`, `--text`, `--muted`, `--border`, `--radius`, `--display`, `--body`.
- **Auto-detect project tokens** from `theme.dart` (Flutter `ColorScheme`/`ThemeData`), `tailwind.config.(js|ts)`, `tokens.json` / Style-Dictionary, or `:root` CSS vars → write `_framework/tokens.css` overrides. Ask the user only if none found.
- **Precedence:** explicit theme pick → auto-detected project tokens → neutral default.
- The **active theme name is recorded in the pixel spec** for handoff (the live switcher is for exploration; the spec captures the locked choice).

## 6. Anatomy of a generated file (top → bottom)

1. **Hero + quickref bar** — flow title + 4 must-know values (reference device · key motion · min tap target · active theme).
2. **Control strip** — live state legend · surface/device selector (grouped phone/tablet/foldable/web) · theme switcher (20+) · light/dark toggle · flow-map toggle.
3. **Interactive playground** — the device frame running the **router**: walk the flow (tap → push next screen, back-stack, tab-bar switching, push/pop/modal transitions), real gestures, real state.
4. **Flow map** — auto-derived screen graph (nodes + edges); click any node to jump there.
5. **State catalog** — frozen frames for every meaningful state **per screen** (default / loading / empty / error / sheet / dark), drift-proof via the state-swap pattern.
6. **Light + dark pair** — one frame each, theme-aware.
7. **Spec sections (flow-spanning):**
   1. Motion + gestures — includes **screen-transition specs** (curve + duration per push/pop/modal).
   2. **Accessibility audit** — *new*; absorbs the old standalone tap-target audit.
   3. Deep-link map — resolves to specific screens in the flow.
   4. Pixel spec — per surface/device · type ramp · components · colours · **active theme name**.
   5. **Interaction matrix** — every tappable → UI feedback · state · API · **target screen** · analytics · error (spans all screens).
   6. Widget-tree mapping — component → Flutter/SwiftUI/Compose widget + package, **plus navigation mapping** (Navigator 2.0 / NavigationStack / Compose Navigation).

## 7. New capabilities, in depth

### 7.1 Multi-screen clickable flows (`router.js` + `flowmap.js`)

**Screen model** — data + a render fn, with *declared* outgoing links:

```js
registerScreen('inbox', {
  title: 'Inbox', tab: 'home',
  render: (ctx) => `…innerHTML…`,   // ctx carries surface, theme, state
  links: ['thread', 'settings'],    // feeds the flow map
});
```

**Router API:** `navigate(id, { mode })` where `mode = push | replace | modal | tab`; a real back-stack with `back()`; `mountTabBar([...])` for persistent tabs (switching a tab swaps the active stack); CSS-class-driven transitions (push slides in from right, pop slides out, modal slides up) that honor `prefers-reduced-motion`. The router swaps only the **inner screen** — frame chrome (status bar, notch, tab bar) persists. It exposes current state so the catalog and flow map read from it (no drift).

**Flow map:** nodes built from registered screens, edges from each screen's `links`; current screen highlighted; click a node → `router.navigate(id, { mode: 'replace' })`. **Auto-derived → cannot drift** from the actual screens; doubles as navigation documentation. Each transition is auto-listed in the motion spec.

### 7.2 More surfaces (`frame.css` + `device-selector.js`)

`frame.css` keys off `data-surface` + `--device-*`:
- **phone** — existing bezel / notch / home-indicator.
- **tablet** — larger bezel, orientation toggle, optional master-detail (two-column) layout.
- **foldable** — two states: **closed** (cover display, phone-like) and **open** (square-ish, hinge crease, optional dual-pane).
- **web** — browser chrome (traffic-lights + URL bar); content reflows at the chosen breakpoint.

**Registry, grouped by surface:**
- Phones: existing 9 (iPhone Pro Max → SE, Pixel, Galaxy).
- Tablets: iPad Pro 13", iPad Pro 11", iPad mini.
- Foldables: Galaxy Z Fold (open + closed), Pixel Fold (open + closed).
- Web: 390 / 768 / 1280 / 1440 breakpoints.

Each profile carries: `name`, `surface`, `os`/`family`, `width`, `height`, `radius`, `notch`, bottom type, `statusH`, `bottomH`, and (where relevant) `orientation`, fold geometry, web-chrome config.

**Surface-adaptive rendering:** screens receive `ctx.surface`, so a screen *can* adapt (master-detail on tablet, stacked on phone). Default: the frame just scales; surface-specific layout is **opt-in per screen** (keeps the MVP small).

### 7.3 Accessibility audit (`a11y.js`)

Auto-computed where possible, guided checklist where not:
- **Contrast** — WCAG ratios for text/bg + key UI pairs from the *active theme*; AA/AAA pass-fail per text size; **recomputes on theme switch**.
- **Tap targets** — measures rendered interactive elements; flags `< 44pt` (iOS) / `48dp` (Material) with locations.
- **Dynamic type** — re-renders the active screen at scales 1.0 / 1.3 / 2.0 / largest; shows reflow & truncation.
- **Semantics** — table of every interactive element → role · accessible label · hint · state (model fills it; structured so nothing is missed).
- **Focus order** — declared traversal order; flags mismatch with visual order.
- **Reduced motion** — confirms each transition has a fallback.

Basis: WCAG 2.2 AA + Apple HIG + Material accessibility.

## 8. Authoring workflow (in `SKILL.md`)

1. **First-time project setup** (skip if `design/_framework/` exists): `mkdir -p design/_framework && cp <skill>/framework/* design/_framework/`. Detect or ask for project tokens; pick a theme or accept neutral.
2. **Per-flow scaffold:** `cp <skill>/template.html design/<flow>.html`. The template's TODO markers: hero copy · quickref values · default theme · seed data · `registerScreen` blocks (render + links) · tab-bar config · catalog state cases · deep-link map · a11y semantics + focus-order tables.
3. **Iterate visually, playground first.** Show the rendered output after every meaningful change (`open design/<flow>.html`, or navigate the `file://` URL with browser MCP). Use the catalog to surface missed states; flip surfaces and themes to verify.
4. **Lock the spec** once visual is approved, in order: state catalog → light/dark pair → motion + gestures (incl. transitions) → accessibility audit → deep-link map → pixel spec → interaction matrix → widget-tree + navigation mapping.

## 9. Distribution & integration

**File layout:**

```
consortium/skills/app-interactive-mocks/
├── SKILL.md
├── README.md
├── framework/   (13 files per §5.2)
├── template.html
└── examples/
    └── <generic-flow>.html   # one full-fat example exercising router + surfaces + themes + a11y
```

- **SKILL.md frontmatter:** `name: app-interactive-mocks`; broadened `description` covering mobile/tablet/web, clickable/walkable flows, interactive prototype, a11y, design spec, "Figma-quality"; trigger phrases ("design mocks", "interactive/clickable prototype", "high-fi mockup", "walkable flow", "spec for the dev", "build me an inbox/profile/settings/checkout screen or flow"); "use BEFORE writing native/Flutter/web UI code for a new screen or flow".
- **Invocation:** auto-trigger via description **and** `/consortium:app-interactive-mocks [flow-name]`. No dedicated command.
- **Manifest touch-ups (non-structural):** broaden `.claude-plugin/plugin.json` `description` + `keywords` to mention design mocks; add a section to the repo `README.md` so people discover it.
- **Example:** replace Aadhaa's `notifications-inbox` with one **generic** full-fat flow (e.g. a 3–4 screen settings or store flow) that exercises the router, flow map, multiple surfaces, theme switching, and the a11y section. Unlike the Aadhaa example, it imports from `_framework/` (canonical wiring).

## 10. Quality bar & anti-patterns

**Quality bar** (carried from original + extended):
- Reference target: iPhone 17 Pro Max (440 × 956 pt); verified at 375 pt (SE) **and** ≥ 1 tablet and ≥ 1 web breakpoint.
- All values in pt (= Flutter logical px = SwiftUI pt = Android dp).
- Catalog renders via state-swap — never duplicated static markup.
- Flow map auto-derived from the router registry — never hand-maintained.
- Interaction matrix covers every tappable element (feedback · state · API · target screen · analytics · error).
- Widget-tree mapping names a specific widget + package per component, plus a navigation mapping.
- Real photographic assets (Unsplash `?w=200&h=200&fit=crop&q=80` / project CDN) — never grey placeholders.
- Themes read from tokens — never hard-coded colours.

**Anti-patterns:**
- Static-only HTML (defeats the purpose) · catalog/playground drift · pixel-perfect at one device only · hover-revealed actions · long-press for primary actions · hard-coded tokens · multi-file flows · skipping the interaction matrix or a11y section.

## 11. Verification plan

Before declaring done, open the generated example via the available browser MCP (Playwright / chrome-devtools) and confirm:
- Router navigation + back-stack (push → pop returns correctly); tab switching preserves per-tab stacks.
- Surface switching: phone → tablet → foldable (open + closed) → web renders cleanly.
- Theme switch across several presets; **contrast recomputes** on switch; light/dark both render.
- Catalog matches the playground (no drift) for each screen's states.
- Layout holds at 375 pt + default phone + a tablet + a web breakpoint.
- `prefers-reduced-motion` disables / reduces transitions.

## 12. Open questions / future

- **Code export** (scaffolded Flutter/SwiftUI/Compose + `tokens.json`) — deferred; revisit after MVP.
- **Short alias command** (`/consortium:mock`) — add only if the full skill name proves annoying.
- **Additional surfaces** — Android tablet, landscape phone, desktop-native chrome — add on demand.
- **Theme count** — final curated list (≥ 23) locked during implementation.
