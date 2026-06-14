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

# ---- Task 2: tokens ----
check "tokens defines --primary"     "--primary:"  "$(cat "$FW/tokens.css" 2>/dev/null)"
check "tokens defines --card"        "--card:"     "$(cat "$FW/tokens.css" 2>/dev/null)"
check "tokens defines --display"     "--display:"  "$(cat "$FW/tokens.css" 2>/dev/null)"
check "tokens has neutral font"      "system-ui"   "$(cat "$FW/tokens.css" 2>/dev/null)"
check "tokens has dark block"        ".dark-tokens" "$(cat "$FW/tokens.css" 2>/dev/null)"
check "tokens is NOT Aadhaa teal"    "" "$(grep -c '#2FA39A' "$FW/tokens.css" 2>/dev/null | grep -x 0 && echo OK_NO_TEAL)"
check "tokens is NOT Aadhaa amber"   "" "$(grep -c '#F5C443' "$FW/tokens.css" 2>/dev/null | grep -x 0 && echo OK_NO_AMBER)"

# ---- Task 3: themes + theme-selector ----
node --check "$FW/theme-selector.js" >/dev/null 2>&1 && echo "ok   - theme-selector.js parses" || { echo "FAIL - theme-selector.js syntax"; fails=$((fails+1)); }
checkge "themes.css has >=20 [data-theme] blocks" 20 "$(grep -c '\[data-theme=' "$FW/themes.css" 2>/dev/null || echo 0)"
checkge "ThemeKit.THEMES has >=20 entries" 20 "$(jeval "console.log(require('$FW/theme-selector.js').THEMES.length)")"
check "every theme id is defined in CSS" "ALL_THEMES_DEFINED" "$(jeval "
  const fs=require('fs');
  const css=fs.readFileSync('$FW/themes.css','utf8');
  const ids=require('$FW/theme-selector.js').THEMES.map(t=>t.id).filter(id=>id!=='neutral');
  const missing=ids.filter(id=>!css.includes('[data-theme=\"'+id+'\"]'));
  console.log(missing.length? 'MISSING:'+missing.join(',') : 'ALL_THEMES_DEFINED');
")"

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

# ---- Task 5: components + icons ----
node --check "$FW/icons.js" >/dev/null 2>&1 && echo "ok   - icons.js parses" || { echo "FAIL - icons.js syntax"; fails=$((fails+1)); }
check "components has .tabbar" ".tabbar" "$(cat "$FW/components.css" 2>/dev/null)"
check "components has .appbar" ".appbar" "$(cat "$FW/components.css" 2>/dev/null)"
check "icons exposes window.I" "window.I" "$(cat "$FW/icons.js" 2>/dev/null)"
check "icons has chevron"  "chevron" "$(cat "$FW/icons.js" 2>/dev/null)"
check "icons has cart"     "cart:"   "$(cat "$FW/icons.js" 2>/dev/null)"

# ---- Task 6: gestures + state-swap ----
node --check "$FW/gestures.js"   >/dev/null 2>&1 && echo "ok   - gestures.js parses"   || { echo "FAIL - gestures.js syntax";   fails=$((fails+1)); }
node --check "$FW/state-swap.js" >/dev/null 2>&1 && echo "ok   - state-swap.js parses" || { echo "FAIL - state-swap.js syntax"; fails=$((fails+1)); }
check "gestures supports long-press" "longPress" "$(cat "$FW/gestures.js" 2>/dev/null)"
check "state-swap keeps withTempState" "function withTempState" "$(cat "$FW/state-swap.js" 2>/dev/null)"
check "catalog supports data-screen"   "data-screen"            "$(cat "$FW/state-swap.js" 2>/dev/null)"

# ---- Task 7: spec-styles ----
check "spec-styles has .flowmap" ".flowmap" "$(cat "$FW/spec-styles.css" 2>/dev/null)"
check "spec-styles has .a11y"    ".a11y"    "$(cat "$FW/spec-styles.css" 2>/dev/null)"
check "spec-styles keeps .quickref" ".quickref" "$(cat "$FW/spec-styles.css" 2>/dev/null)"

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
