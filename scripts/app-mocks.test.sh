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

# ---- Task 8: router ----
# rcheck: invoke the pure reducer via node, avoiding bash brace-expansion on {..,.}
rcheck() { # rcheck "desc" "expected" 'stack_json' 'action_json'
  local js="const R=require(\"$FW/router.js\"); console.log(R._reduce($3,$4).join(\",\"));"
  check "$1" "$2" "$(node -e "$js" 2>&1)"
}
node --check "$FW/router.js" >/dev/null 2>&1 && echo "ok   - router.js parses" || { echo "FAIL - router.js syntax"; fails=$((fails+1)); }
rcheck "push appends to stack"  "a,b"   '["a"]'         '{type:"push",id:"b"}'
rcheck "replace swaps top"      "a,c"   '["a","b"]'     '{type:"replace",id:"c"}'
rcheck "pop removes top"        "a"     '["a","b"]'      '{type:"pop"}'
rcheck "pop keeps root"         "a"     '["a"]'          '{type:"pop"}'
rcheck "tab resets to root"     "home"  '["a","b","c"]'  '{type:"tab",id:"home"}'

# ---- Task 9: flowmap ----
node --check "$FW/flowmap.js" >/dev/null 2>&1 && echo "ok   - flowmap.js parses" || { echo "FAIL - flowmap.js syntax"; fails=$((fails+1)); }
check "deriveGraph yields nodes" "2" "$(node -e 'const F=require(process.argv[1]); const s={a:{id:"a",links:["b"]},b:{id:"b",links:[]}}; console.log(F.deriveGraph(s).nodes.length)' "$FW/flowmap.js" 2>&1)"
check "deriveGraph yields edges" "a->b" "$(node -e 'const F=require(process.argv[1]); const s={a:{id:"a",links:["b"]},b:{id:"b",links:[]}}; const g=F.deriveGraph(s); console.log(g.edges.map(e=>e.from+"->"+e.to).join(","))' "$FW/flowmap.js" 2>&1)"
check "deriveGraph drops dangling edges" "EDGES=0" "$(node -e 'const F=require(process.argv[1]); const s={a:{id:"a",links:["ghost"]}}; console.log("EDGES="+F.deriveGraph(s).edges.length)' "$FW/flowmap.js" 2>&1)"

# ---- Task 11: a11y ----
node --check "$FW/a11y.js" >/dev/null 2>&1 && echo "ok   - a11y.js parses" || { echo "FAIL - a11y.js syntax"; fails=$((fails+1)); }
check "contrast black/white = 21" "21" "$(jeval "const A=require('$FW/a11y.js'); console.log(Math.round(A.contrastRatio('#000000','#ffffff')))")"
check "wcag 21 is AAA"   "AAA"  "$(jeval "const A=require('$FW/a11y.js'); console.log(A.wcagLevel(A.contrastRatio('#000000','#ffffff'),{large:false}))")"
check "wcag low is fail" "fail" "$(jeval "const A=require('$FW/a11y.js'); console.log(A.wcagLevel(A.contrastRatio('#999999','#ffffff'),{large:false}))")"
check "exposes mountAudit" "mountAudit" "$(cat "$FW/a11y.js" 2>/dev/null)"

# ---- Task 10: template + example ----
check "template loads themes.css"      "_framework/themes.css"   "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template loads router.js"       "_framework/router.js"    "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template loads flowmap.js"      "_framework/flowmap.js"   "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template loads a11y.js"         "_framework/a11y.js"      "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template registers a screen"    "registerScreen"          "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template mounts theme selector" "mountThemeSelector"      "$(cat "$SKILL/template.html" 2>/dev/null)"
check "template mounts flow map"       "Flowmap.mount"           "$(cat "$SKILL/template.html" 2>/dev/null)"
check "example imports framework"      "../framework/router.js"  "$(cat "$SKILL/examples/shop-flow.html" 2>/dev/null)"
check "example registers >=3 screens"  "SCREENS_OK" "$(c=$(grep -c 'registerScreen' "$SKILL/examples/shop-flow.html" 2>/dev/null || echo 0); [ "$c" -ge 3 ] && echo SCREENS_OK || echo "ONLY_$c")"
check "example uses real images"       "images.unsplash.com"     "$(cat "$SKILL/examples/shop-flow.html" 2>/dev/null)"
check "example has no TODO markers"    "NO_TODO" "$(grep -qi 'TODO' "$SKILL/examples/shop-flow.html" && echo HAS_TODO || echo NO_TODO)"

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
