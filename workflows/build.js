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
const extraReviewers = a && Array.isArray(a.extraReviewers) ? a.extraReviewers : [] // conditional reviewers (by change-type), chosen by the skill
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
  gate = await agent(`Spec gate: read \`git diff\` and the changed files line by line; map every plan requirement to the diff and check scope boundaries and do-not-change values word for word. Does the diff implement the plan, accurately and completely? For this legacy workflow, return only the GATE object: verdict COMPLIANT or NOT_COMPLIANT and discrepancies as strings, rather than the factory report envelope.\n\nPLAN:\n${plan}`,
    { agentType: 'consortium:spec-gate', label: 'gate:r' + round, phase: 'Review', schema: GATE })

  if (gate.verdict === 'COMPLIANT') {
    const reviewerTasks = [
      () => agent('Read `git diff`, affected callers and tests; review correctness, error handling and silent failures, and the repo\'s conventions and reuse. Also suggest quality-only simplifications that cut length and vagueness without changing behavior; tag meaningful simplifications "important". Remain read-only and run no tests. For this legacy workflow, return only FINDINGS: { reviewer, findings: [{ severity: "blocking" | "important" | "minor", issue, suggestion }] }, rather than the factory report envelope.', { agentType: 'consortium:code-reviewer', label: 'code:r' + round, phase: 'Review', schema: FINDINGS }),
    ]
    // Conditional reviewers (by change-type) the skill passed in — dispatched alongside the always-on experts.
    for (const t of new Set(extraReviewers)) {
      const focus = t === 'consortium:test-designer'
        ? `Use trace mode: read the approved plan, any supplied design-derived positive and negative cases, tests and passing gate logs. Identify missing coverage and unavailable passing evidence for logic and behavior changes; never infer a pass from a test's name or existence. Run no tests.\n\nPLAN:\n${plan}`
        : t === 'consortium:infra-reviewer'
          ? 'Read `git diff` and related definitions; review infrastructure and CI/CD for resource replacement, data loss, IAM, drift, pipeline security, and every allowlist and route registry named by the repository notes. Inspect supplied plans and logs only; remain read-only and run no tests or pipelines.'
          : 'Run `git diff`; review the change for your specialty. Return findings.'
      reviewerTasks.push(() => agent(focus + '\nFor this legacy workflow, return only FINDINGS: { reviewer, findings: [{ severity: "blocking" | "important" | "minor", issue, suggestion }] }, rather than the factory report envelope. Report missing required review evidence as findings.', { agentType: t, label: String(t).replace('consortium:', '') + ':r' + round, phase: 'Review', schema: FINDINGS }))
    }
    reviews = await parallel(reviewerTasks)
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
