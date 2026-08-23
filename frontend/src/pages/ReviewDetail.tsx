import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  ArrowsClockwise,
  CheckCircle,
  FileText,
  GearSix,
  ListChecks,
  ShieldCheck,
  WarningCircle,
} from '@phosphor-icons/react'
import { api } from '../api/client'
import { Stepper } from '../components/Stepper'
import { VerdictBanner } from '../components/VerdictBanner'
import { useReview } from '../hooks/useReviews'
import type { Decision, TestLevel } from '../types'

function Card({ title, icon, children }: { title: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-background p-5">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-foreground/60">
        {icon}
        {title}
      </h2>
      {children}
    </section>
  )
}

function ChipList({ items }: { items: string[] }) {
  if (!items?.length) return <p className="text-sm text-foreground/50">—</p>
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item, i) => (
        <span key={i} className="rounded-full border border-border bg-muted px-3 py-1 text-xs">
          {item}
        </span>
      ))}
    </div>
  )
}

export function ReviewDetail() {
  const { id } = useParams<{ id: string }>()
  const { review, error, loading } = useReview(id)
  const [overriding, setOverriding] = useState(false)
  const [override, setOverride] = useState<Decision | null>(null)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)

  const agent = review?.llm_decision
  const final = review?.final_decision
  const overridden = useMemo(() => {
    if (!agent || !final) return false
    return (
      agent.test_level !== final.test_level ||
      agent.requires_pentest !== final.requires_pentest
    )
  }, [agent, final])

  if (loading && !review) return <p className="text-sm text-foreground/50">Loading review…</p>
  if (error) return <p className="text-sm text-destructive">Failed to load: {error}</p>
  if (!review) return <p className="text-sm text-destructive">Review not found.</p>

  const saveOverride = async () => {
    if (!override) return
    setSaveMsg(null)
    try {
      await api.setDecision(review.id, override)
      setSaveMsg('Final decision saved.')
      setOverriding(false)
      setOverride(null)
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">Security Review</h1>
            <p className="mt-0.5 font-mono text-xs text-foreground/50">
              {review.frd_name} + {review.nfrd_name} · {new Date(review.created_at).toLocaleString()}
            </p>
          </div>
          <span
            className={`rounded-full border px-3 py-1 font-mono text-xs ${
              review.status === 'completed'
                ? 'border-accent/40 bg-accent/10 text-accent'
                : review.status === 'failed'
                  ? 'border-destructive/40 bg-destructive/10 text-destructive'
                  : 'border-secondary/40 bg-secondary/10 text-secondary animate-pulse'
            }`}
          >
            {review.status}
          </span>
        </div>
      </header>

      {review.status === 'running' && (
        <div className="rounded-xl border border-border bg-background p-8 text-center">
          <Stepper
            current={
              review.facts
                ? review.retrieved_sources.length
                  ? review.rules_fired.length
                    ? 3
                    : 2
                  : 1
                : 0
            }
            running
          />
          <p className="mt-6 flex items-center justify-center gap-2 text-sm text-foreground/60">
            <ArrowsClockwise size={16} className="animate-spin" />
            Running local analysis… this page refreshes automatically.
          </p>
        </div>
      )}

      {review.status === 'failed' && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
          <p className="font-semibold">The review failed.</p>
          <p className="mt-1">{review.error}</p>
        </div>
      )}

      {review.status === 'completed' && final && (
        <div className="space-y-6">
          <VerdictBanner decision={final} overridden={overridden} />

          {review.conflicts.length > 0 && (
            <div className="rounded-xl border border-warning/40 bg-warning/10 p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-warning">
                <WarningCircle size={18} weight="fill" />
                Rule engine disagrees with the agent
              </h3>
              <ul className="mt-2 space-y-1 text-sm">
                {review.conflicts.map((c, i) => (
                  <li key={i}>
                    <span className="font-mono text-xs text-warning/80">{c.field}:</span> {c.explanation}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-foreground/60">
                Rules say <strong>{review.rule_test_level}</strong>; the agent recommended{' '}
                <strong>{agent?.test_level}</strong>. Confirm the final decision below.
              </p>
            </div>
          )}

          <Card title="Reasoning" icon={<FileText size={16} />}>
            <p className="text-sm leading-relaxed text-foreground/85">
              {final.classification_reason}
            </p>
            {final.risk_factors.length > 0 && (
              <div className="mt-4">
                <p className="mb-2 text-xs font-medium text-foreground/60">Risk factors</p>
                <ChipList items={final.risk_factors} />
              </div>
            )}
            {final.recommended_frameworks.length > 0 && (
              <div className="mt-4">
                <p className="mb-2 text-xs font-medium text-foreground/60">Compliance frameworks</p>
                <ChipList items={final.recommended_frameworks} />
              </div>
            )}
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card title="Scope — in scope" icon={<ShieldCheck size={16} />}>
              <ChipList items={final.scope.in_scope} />
              <p className="mt-4 mb-2 text-xs font-medium text-foreground/60">Out of scope</p>
              <ChipList items={final.scope.out_of_scope} />
            </Card>
            <Card title="How to test" icon={<GearSix size={16} />}>
              <ChipList items={final.scope.test_methods} />
              <p className="mt-4 mb-2 text-xs font-medium text-foreground/60">Environments</p>
              <ChipList items={final.scope.environments} />
              {final.scope.effort_estimate && (
                <p className="mt-4 text-sm text-foreground/80">
                  <span className="font-medium">Effort:</span> {final.scope.effort_estimate}
                </p>
              )}
            </Card>
          </div>

          <Card title="Deterministic rules that fired" icon={<ListChecks size={16} />}>
            {review.rules_fired.length === 0 ? (
              <p className="text-sm text-foreground/50">No rules matched.</p>
            ) : (
              <ul className="space-y-3">
                {review.rules_fired.map((r) => (
                  <li key={r.id} className="rounded-lg border border-border bg-muted/40 p-3">
                    <p className="text-sm font-semibold">
                      <span className="font-mono text-xs text-secondary">{r.id}</span> · {r.name}
                      <span className="ml-2 rounded-full bg-border/60 px-2 py-0.5 font-mono text-[10px] uppercase text-foreground/60">
                        {r.test_level}
                      </span>
                    </p>
                    <p className="mt-1 text-xs text-foreground/70">{r.reasoning}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card title="Retrieved knowledge base sources" icon={<CheckCircle size={16} />}>
            {review.retrieved_sources.length === 0 ? (
              <p className="text-sm text-foreground/50">
                No SOP/policy/previous-review content was retrieved. Add documents to the knowledge
                base for more grounded decisions.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {review.retrieved_sources.map((s, i) => (
                  <li key={i} className="flex items-center gap-2 font-mono text-xs">
                    <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
                    {s}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Human override */}
          <Card title="Final decision (human override)" icon={<GearSix size={16} />}>
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={overriding ? override?.requires_pentest ?? false : final.requires_pentest}
                  onChange={(e) =>
                    setOverride((o) => ({
                      ...(o ?? final),
                      requires_pentest: e.target.checked,
                    }))
                  }
                  disabled={!overriding}
                  className="h-4 w-4 accent-primary"
                />
                Pentest required
              </label>
              <div className="flex items-center gap-2">
                {(['dast', 'pentest', 'both', 'none'] as TestLevel[]).map((level) => (
                  <button
                    key={level}
                    disabled={!overriding}
                    onClick={() =>
                      setOverride((o) => ({
                        ...(o ?? final),
                        test_level: level,
                        requires_pentest: level === 'pentest' || level === 'both',
                      }))
                    }
                    className={`rounded-lg border px-3 py-1.5 font-mono text-xs uppercase transition-colors ${
                      (overriding ? override?.test_level : final.test_level) === level
                        ? 'border-primary bg-primary/10 font-bold text-primary'
                        : 'border-border hover:border-primary/40'
                    } disabled:cursor-not-allowed`}
                  >
                    {level}
                  </button>
                ))}
              </div>
              <div className="ml-auto flex gap-2">
                {!overriding ? (
                  <button
                    onClick={() => {
                      setOverride(structuredClone(final))
                      setOverriding(true)
                    }}
                    className="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
                  >
                    Override
                  </button>
                ) : (
                  <>
                    <button
                      onClick={() => {
                        setOverriding(false)
                        setOverride(null)
                      }}
                      className="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => void saveOverride()}
                      className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90"
                    >
                      Save final decision
                    </button>
                  </>
                )}
              </div>
            </div>
            {saveMsg && <p className="mt-2 text-xs text-foreground/70">{saveMsg}</p>}
          </Card>
        </div>
      )}
    </div>
  )
}
