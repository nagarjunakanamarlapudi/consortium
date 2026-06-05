export const meta = {
  name: 'consortium-build',
  description: 'Build phase as one workflow: parallel implementation (disjoint files) -> spec-compliance gate -> advisory experts [+ bar-raiser] -> fix loop. Returns the final review state.',
  phases: [{ title: 'Implement' }, { title: 'Review' }],
}

// args arrives at the script as a JSON STRING (runtime behavior) — always parse defensively.
let a = args
if (typeof a === 'string') { try { a = JSON.parse(a) } catch (e) { a = {} } }
const plan = (a && a.plan) || ''
const chunks = a && Array.isArray(a.chunks) ? a.chunks : null // optional disjoint-file task specs
const barRaiser = !!(a && a.barRaiser)
const maxRounds = (a && a.maxRounds) || 3
if (!plan && !chunks) log('No args.plan/chunks provided; implementer relies on repo context only.')

const GATE = { type: 'object', properties: { verdict: { enum: ['COMPLIANT', 'NOT_COMPLIANT'] }, discrepancies: { type: 'array', items: { type: 'string' } } }, required: ['verdict'] }
const FINDINGS = { type: 'object', properties: { reviewer: { type: 'string' }, findings: { type: 'array', items: { type: 'object', properties: { severity: { enum: ['blocking', 'important', 'minor'] }, issue: { type: 'string' }, suggestion: { type: 'string' } }, required: ['severity', 'issue'] } } }, required: ['reviewer', 'findings'] }
const VERDICT = { type: 'object', properties: { verdict: { enum: ['accept', 'reject'] }, rigor_score: { type: 'number' }, rewrite_mandates: { type: 'array', items: { type: 'object', properties: { severity: { enum: ['minor', 'major'] }, mandate: { type: 'string' } }, required: ['severity', 'mandate'] } } }, required: ['verdict', 'rigor_score'] }

// 1. Implement — parallel over disjoint chunks if given, else a single implementer for the whole plan.
phase('Implement')
if (chunks && chunks.length) {
  await parallel(chunks.map((c, i) => () =>
    agent(`Implement your part of the plan. Touch ONLY these files: ${(c.files || []).join(', ')}.\n\n${c.instructions || plan}`,
      { agentType: 'consortium:implementer', label: 'impl:' + i, phase: 'Implement' })))
} else {
  await agent(`Implement this plan faithfully.\n\nPLAN:\n${plan}`,
    { agentType: 'consortium:implementer', label: 'impl', phase: 'Implement' })
}

// 2. Review + fix loop (spec-compliance gate -> advisory experts [+ bar-raiser] -> implementer fixes -> repeat).
phase('Review')
let round = 0
let gate = null
let reviews = []
let verdict = null
while (true) {
  gate = await agent(`Spec-compliance gate: run \`git diff\` and read the changed files; does the diff implement the plan, accurately and completely?\n\nPLAN:\n${plan}`,
    { agentType: 'consortium:spec-compliance-reviewer', label: 'gate:r' + round, phase: 'Review', schema: GATE })

  if (gate.verdict === 'COMPLIANT') {
    reviews = await parallel([
      () => agent('Run `git diff`; review the change for code quality. Return findings.', { agentType: 'consortium:code-quality-reviewer', label: 'cq:r' + round, phase: 'Review', schema: FINDINGS }),
      () => agent('Run `git diff`; review the change for repo conventions & reuse. Return findings.', { agentType: 'consortium:domain-conventions-reviewer', label: 'dc:r' + round, phase: 'Review', schema: FINDINGS }),
    ])
    verdict = barRaiser
      ? await agent('Bar-raiser: run `git diff`; review the change against a high bar. Return your verdict.', { agentType: 'consortium:bar-raiser', label: 'br:r' + round, phase: 'Review', schema: VERDICT })
      : null
  } else {
    reviews = []
    verdict = null
  }

  const important = reviews.filter(Boolean).flatMap((r) => r.findings || []).filter((f) => f.severity === 'blocking' || f.severity === 'important')
  const needsFix = gate.verdict === 'NOT_COMPLIANT' || (verdict && verdict.verdict === 'reject') || important.length > 0
  if (!needsFix) break
  round++
  if (round >= maxRounds) break

  const mandates = []
  if (gate.verdict === 'NOT_COMPLIANT') for (const d of gate.discrepancies || []) mandates.push('[spec] ' + d)
  if (verdict && verdict.rewrite_mandates) for (const m of verdict.rewrite_mandates) mandates.push('[' + m.severity + '] ' + m.mandate)
  for (const f of important) mandates.push('[' + f.severity + '] ' + f.issue + (f.suggestion ? ' -- ' + f.suggestion : ''))

  await agent('Apply these fixes (redesign where mandated; do not patch around):\n' + mandates.join('\n'),
    { agentType: 'consortium:implementer', label: 'fix:r' + round, phase: 'Review' })
}

return { rounds: round, gate, reviews: reviews.filter(Boolean), barRaiser: verdict }
