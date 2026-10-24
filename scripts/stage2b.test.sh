#!/usr/bin/env bash
# Structural + syntax checks for the workflow engine (Stage 2b). Behavior verified live (installed session).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fails=0; ok(){ printf 'ok   - %s\n' "$1"; }; fail(){ printf 'FAIL - %s\n' "$1"; fails=$((fails+1)); }
# node --check passes any file that uses `export`, even one with a syntax error (Node 24), so compile the script the
# way the workflow runtime runs it: as an async function body, with meta no longer exported.
compiles(){ node -e 'new (Object.getPrototypeOf(async function () {}).constructor)("args", "agent", "parallel", "phase", "log",
  require("fs").readFileSync(process.argv[1], "utf8").replace("export const meta =", "const meta ="))' "$1" 2>/dev/null; }

js="$ROOT/workflows/plan-review.js"
# 1. script present with meta + reviewer agentTypes + schema + parallel
if [ -f "$js" ] && grep -q "export const meta" "$js" && grep -q "consortium:test-designer" "$js" && grep -q "schema" "$js" && grep -q "parallel" "$js"; then ok "plan-review.js present (meta, reviewer agentTypes, schema, parallel)"; else fail "plan-review.js missing/incomplete"; fi

# 2. JS syntax valid (compiling does not run the script, so workflow globals are fine)
if command -v node >/dev/null 2>&1; then
  if compiles "$js"; then ok "plan-review.js compiles"; else fail "plan-review.js has a syntax error"; fi
else
  ok "node unavailable — syntax check skipped"
fi

# 3. README documents invocation (${CLAUDE_PLUGIN_ROOT}) + fallback
r="$ROOT/workflows/README.md"
if [ -f "$r" ] && grep -q "CLAUDE_PLUGIN_ROOT" "$r" && grep -qi "fallback" "$r"; then ok "workflows/README documents invocation + fallback"; else fail "workflows/README missing/incomplete"; fi

# 4. experts-eval playbook prefers the workflow with an explicit fallback
pb="$ROOT/skills/team-dev-workflow/references/experts-eval.md"
if grep -q "plan-review.js" "$pb" && grep -qi "fallback" "$pb"; then ok "experts-eval prefers the workflow with fallback"; else fail "experts-eval not wired to the workflow"; fi

# 5. build.js present with meta + implementer + reviewer agentTypes + schema
js2="$ROOT/workflows/build.js"
if [ -f "$js2" ] && grep -q "export const meta" "$js2" && grep -q "consortium:implementer" "$js2" && grep -q "consortium:spec-gate" "$js2" && grep -q "consortium:bar-raiser" "$js2" && grep -q "schema" "$js2"; then ok "build.js present (meta, implementer + reviewer agentTypes, schema)"; else fail "build.js missing/incomplete"; fi

# 6. build.js syntax
if command -v node >/dev/null 2>&1; then compiles "$js2" && ok "build.js compiles" || fail "build.js syntax error"; else ok "node unavailable — build.js syntax check skipped"; fi

# 7. implementer agent present with frontmatter
ia="$ROOT/agents/implementer.md"
if [ -f "$ia" ] && grep -q "^name: implementer$" "$ia"; then ok "implementer agent present"; else fail "implementer agent missing"; fi

# 8. build + vibe wired to build.js
if grep -q "build.js" "$pb" && grep -q "build.js" "$ROOT/skills/team-dev-workflow/references/bar-raiser-eval.md" && grep -q "build.js" "$ROOT/skills/team-dev-workflow/references/vibe-coding.md"; then ok "build + vibe wired to build.js"; else fail "build/vibe not wired to build.js"; fi

# 9. Combined quality reviewer present + wired into build.js
if [ -f "$ROOT/agents/code-reviewer.md" ] && grep -q "^name: code-reviewer$" "$ROOT/agents/code-reviewer.md" && grep -q "consortium:code-reviewer" "$js2"; then ok "code-reviewer present + wired into build.js"; else fail "code-reviewer missing/not wired"; fi

# 10. Execute the workflows with a controlled agent boundary: gate ordering,
# dispatch counts, schemas, conditional reviewers, and the fix loop are contracts.
if command -v node >/dev/null 2>&1; then
  if node - "$ROOT" <<'JS'
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const root = process.argv[2]
const findings = (reviewer, items = []) => ({ reviewer, findings: items })

async function run(file, args, respond) {
  const calls = []
  const source = fs.readFileSync(path.join(root, 'workflows', file), 'utf8')
    .replace('export const meta =', 'const meta =')
  const workflow = new AsyncFunction('args', 'agent', 'parallel', 'phase', 'log', source)
  const result = await workflow(args, async (prompt, options) => {
    calls.push({ prompt, ...options })
    return respond(options, prompt)
  }, tasks => Promise.all(tasks.map(task => task())), () => {}, () => {})
  return { result, calls }
}

async function main() {
  const plan = 'Add validation with acceptance and rejection cases.'
  const planned = await run('plan-review.js', JSON.stringify({
    plan, extraReviewers: ['other:plan-reviewer'],
  }), ({ agentType, schema }, prompt) => {
    assert.deepEqual(schema.required, ['reviewer', 'findings'])
    assert.ok(prompt.includes(plan))
    return agentType === 'other:plan-reviewer' ? null : findings(agentType)
  })
  assert.deepEqual(planned.calls.map(c => c.agentType), [
    'consortium:test-designer', 'other:plan-reviewer',
  ])
  assert.deepEqual(planned.result.reviews, [findings('consortium:test-designer')])

  const built = await run('build.js', JSON.stringify({
    plan, barRaiser: true,
    extraReviewers: ['consortium:infra-reviewer', 'consortium:infra-reviewer',
      'consortium:test-designer', 'consortium:security-reviewer'],
  }), ({ agentType, schema, label }, prompt) => {
    if (agentType === 'consortium:implementer') return {}
    if (agentType === 'consortium:spec-gate') {
      assert.deepEqual(schema.properties.verdict.enum, ['COMPLIANT', 'NOT_COMPLIANT'])
      assert.deepEqual(schema.required, ['verdict'])
      assert.ok(prompt.includes(plan))
      return { verdict: 'COMPLIANT' }
    }
    if (agentType === 'consortium:bar-raiser') return { verdict: 'accept', rigor_score: 4 }
    assert.deepEqual(schema.required, ['reviewer', 'findings'])
    assert.deepEqual(schema.properties.findings.items.properties.severity.enum,
      ['blocking', 'important', 'minor'])
    return findings(agentType, agentType === 'consortium:code-reviewer' && label.endsWith(':r0')
      ? [{ severity: 'important', issue: 'Reuse the existing helper', suggestion: 'Remove duplication' }]
      : [])
  })
  const reviewers = ['consortium:code-reviewer', 'consortium:infra-reviewer',
    'consortium:test-designer', 'consortium:security-reviewer', 'consortium:bar-raiser']
  assert.deepEqual(built.calls.map(c => c.agentType), [
    'consortium:implementer', 'consortium:spec-gate', ...reviewers,
    'consortium:implementer', 'consortium:spec-gate', ...reviewers,
  ])
  assert.match(built.calls.find(c => c.label === 'fix:r1').prompt, /Reuse the existing helper -- Remove duplication/)
  assert.equal(built.result.rounds, 1)
  assert.equal(built.result.gate.verdict, 'COMPLIANT')
  assert.equal(built.result.reviews.length, 4)
  assert.equal(built.result.barRaiser.verdict, 'accept')

  const rejected = await run('build.js', { plan, maxRounds: 2 }, ({ agentType }) => {
    if (agentType === 'consortium:implementer') return {}
    assert.equal(agentType, 'consortium:spec-gate')
    return { verdict: 'NOT_COMPLIANT', discrepancies: ['Missing rejection case'] }
  })
  assert.deepEqual(rejected.calls.map(c => c.agentType), [
    'consortium:implementer', 'consortium:spec-gate',
    'consortium:implementer', 'consortium:spec-gate',
  ])
  assert.match(rejected.calls[2].prompt, /\[spec\] Missing rejection case/)
  assert.equal(rejected.result.rounds, 2)
  assert.deepEqual(rejected.result.reviews, [])
  assert.equal(rejected.result.barRaiser, null)
}

main().catch(error => { console.error(error); process.exitCode = 1 })
JS
  then ok "workflow dispatch, schemas, gates, and fix loop pass"; else fail "workflow behavior failed"; fi
else
  ok "node unavailable — workflow behavior checks skipped"
fi

printf '\n%s failure(s)\n' "$fails"
[ "$fails" -eq 0 ]
