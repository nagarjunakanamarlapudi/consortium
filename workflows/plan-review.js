export const meta = {
  name: 'consortium-plan-review',
  description: 'Fan out the plan reviewers (always-on + auto-discovered project reviewers) and return their structured findings',
  phases: [{ title: 'Plan review' }],
}

const FINDINGS = {
  type: 'object',
  properties: {
    reviewer: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { enum: ['blocking', 'important', 'minor'] },
          issue: { type: 'string' },
          suggestion: { type: 'string' },
        },
        required: ['severity', 'issue'],
      },
    },
  },
  required: ['reviewer', 'findings'],
}

// args arrives at the script as a JSON STRING (runtime behavior) — always parse defensively.
let a = args
if (typeof a === 'string') { try { a = JSON.parse(a) } catch (e) { a = {} } }
const plan = (a && a.plan) || ''
const extraReviewers = a && Array.isArray(a.extraReviewers) ? a.extraReviewers : [] // auto-discovered project plan-reviewers (bare names), chosen by the skill
if (!plan) log('No args.plan provided; reviewers will rely on repo context only.')

const PLAN_PROMPT = `You are reviewing an implementation PLAN for the current repo. Read the repo as needed for grounding.\n\nPLAN:\n${plan}\n\nReturn your findings.`

// Always-on plan reviewers (mirrors references/reviewer-registry.md).
const tasks = [
  () => agent(PLAN_PROMPT, { agentType: 'consortium:spec-clarity-reviewer', label: 'plan:spec-clarity', phase: 'Plan review', schema: FINDINGS }),
  () => agent(PLAN_PROMPT, { agentType: 'consortium:domain-conventions-reviewer', label: 'plan:domain-conventions', phase: 'Plan review', schema: FINDINGS }),
]
// Auto-discovered project plan-reviewers (bare agent names from the repo's .claude/agents/).
for (const t of extraReviewers) {
  tasks.push(() => agent(PLAN_PROMPT, { agentType: t, label: String(t).replace('consortium:', '') + ':plan', phase: 'Plan review', schema: FINDINGS }))
}

const reviews = await parallel(tasks)
return { reviews: reviews.filter(Boolean) }
