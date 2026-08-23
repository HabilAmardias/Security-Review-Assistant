import type { Decision, TestLevel } from '../types'

const LEVEL_META: Record<TestLevel, { label: string; cls: string; hint: string }> = {
  pentest: {
    label: 'Penetration test required',
    cls: 'border-destructive/40 bg-destructive/10 text-destructive',
    hint: 'Manual pentest needed',
  },
  both: {
    label: 'Pentest + DAST required',
    cls: 'border-destructive/40 bg-destructive/10 text-destructive',
    hint: 'Full security testing',
  },
  dast: {
    label: 'DAST scan required',
    cls: 'border-warning/40 bg-warning/10 text-warning',
    hint: 'Automated scanning sufficient',
  },
  none: {
    label: 'No dedicated testing required',
    cls: 'border-accent/40 bg-accent/10 text-accent',
    hint: 'Proceed with standard checks',
  },
}

export function VerdictBanner({
  decision,
  overridden = false,
}: {
  decision: Decision
  overridden?: boolean
}) {
  const meta = LEVEL_META[decision.test_level] ?? LEVEL_META.dast
  return (
    <div
      className={`rounded-xl border-2 px-6 py-5 ${meta.cls}`}
      role="status"
      aria-label={`Verdict: ${meta.label}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className={`h-3 w-3 rounded-full ${
              decision.test_level === 'dast' || decision.test_level === 'none'
                ? 'bg-current'
                : 'bg-current'
            }`}
            aria-hidden
          />
          <h2 className="text-xl font-bold">{meta.label}</h2>
          {overridden && (
            <span className="rounded-full border border-border bg-background px-2.5 py-0.5 text-xs text-foreground/70">
              Human override
            </span>
          )}
        </div>
        <span className="font-mono text-sm opacity-80">{meta.hint}</span>
      </div>
    </div>
  )
}
