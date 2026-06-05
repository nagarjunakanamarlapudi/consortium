export const meta = {
  name: 'consortium-plan-review',
  description: 'Fan out the experts-eval plan reviewers and return their structured findings',
  phases: [{ title: 'Plan review' }],
}

// Each reviewer returns findings in this shape (schema-validated by the runtime).
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

// The plan text is passed in by the skill; agents read the repo themselves for grounding.
const plan = (args && args.plan) || ''
if (!plan) log('No args.plan provided; reviewers will rely on repo context only.')

// Always-on plan reviewers (mirrors references/reviewer-registry.md).
const REVIEWERS = [
  { agentType: 'consortium:spec-clarity-reviewer', label: 'plan:spec-clarity' },
  { agentType: 'consortium:domain-conventions-reviewer', label: 'plan:domain-conventions' },
]

const reviews = await parallel(
  REVIEWERS.map((rv) => () =>
    agent(
      `You are reviewing an implementation PLAN for the current repo. Read the repo as needed for grounding.\n\nPLAN:\n${plan}\n\nReturn your findings.`,
      { agentType: rv.agentType, label: rv.label, phase: 'Plan review', schema: FINDINGS },
    ),
  ),
)

return { reviews: reviews.filter(Boolean) }
