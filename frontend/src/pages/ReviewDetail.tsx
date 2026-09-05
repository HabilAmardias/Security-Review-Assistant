import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowsClockwise,
  CheckCircle,
  FileText,
  GearSix,
  Globe,
  ListChecks,
  ShieldCheck,
  Trash,
  WarningCircle,
} from '@phosphor-icons/react'
import { api } from '../api/client'
import { Stepper, type Step } from '../components/Stepper'
import { VerdictBanner } from '../components/VerdictBanner'
import { useReview } from '../hooks/useReviews'
import type { Analysis, Decision, TestLevel } from '../types'

const THREAT_STEPS: Step[] = [
  { key: 'diagrams', label: 'Read diagrams' },
  { key: 'requirement', label: 'Requirement' },
  { key: 'architecture', label: 'Architecture' },
  { key: 'assets', label: 'Assets' },
  { key: 'threats', label: 'STRIDE' },
  { key: 'decision', label: 'Decide' },
]

const EXPOSURE_LABELS: Record<string, string> = {
  internal: 'Intranet',
  'internet-facing': 'Internet-facing',
  partner: 'Partner / External',
  unclear: 'Unclear',
}

const CHANGE_SCOPE_LABELS: Record<string, string> = {
  limited_change: 'Limited change (no logic impact)',
  feature_change: 'Feature change',
  full_new_app: 'New application',
  other: 'Other',
}

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

function LabeledChips({ label, items }: { label: string; items?: string[] }) {
  if (!items || items.length === 0) return null
  return (
    <div className="mt-3">
      <p className="mb-1 text-xs font-medium text-foreground/60">{label}</p>
      <ChipList items={items} />
    </div>
  )
}

const SEVERITY_CLS: Record<string, string> = {
  critical: 'border-destructive/40 bg-destructive/10 text-destructive',
  high: 'border-warning/40 bg-warning/10 text-warning',
  medium: 'border-secondary/40 bg-secondary/10 text-secondary',
  low: 'border-accent/40 bg-accent/10 text-accent',
}

function SeverityBadge({ severity }: { severity: string }) {
  const s = String(severity || '').toLowerCase()
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase ${SEVERITY_CLS[s] ?? SEVERITY_CLS.low}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {severity || '—'}
    </span>
  )
}

// Read-only rendering of the staged threat-model artifacts.
function ThreatStages({ analysis }: { analysis: Analysis }) {
  const req = analysis.requirement
  const arch = analysis.architecture
  const assets = analysis.assets
  const threats = analysis.threats
  const diagrams = analysis.diagrams

  return (
    <div className="space-y-6">
      {diagrams && diagrams.diagrams.length > 0 && (
        <Card title="Diagrams read" icon={<CheckCircle size={16} />}>
          <p className="text-sm text-foreground/85">{diagrams.summary || 'Diagram understood by the vision model.'}</p>
          {diagrams.diagrams.map((d, i) => (
            <div key={i} className="mt-3 rounded-lg border border-border bg-muted/40 p-3">
              <p className="text-sm font-medium">{d.label || `Diagram ${i + 1}`}</p>
              <LabeledChips label="Actors" items={d.actors} />
              <LabeledChips label="Use cases" items={d.use_cases} />
              <LabeledChips label="Flows" items={d.flows} />
              <LabeledChips label="External systems" items={d.external_systems} />
              {d.notes && <p className="mt-2 text-xs text-foreground/70">{d.notes}</p>}
            </div>
          ))}
        </Card>
      )}

      {req && (
        <Card title="Requirement" icon={<FileText size={16} />}>
          <p className="text-sm leading-relaxed text-foreground/85">{req.summary}</p>
          <LabeledChips label="What is submitted" items={req.data_submitted} />
          <LabeledChips label="Who submits / uses" items={req.actors} />
          <LabeledChips label="Where it goes" items={req.destinations} />
          <LabeledChips label="Who can approve" items={req.approvers} />
          <LabeledChips label="Triggers" items={req.triggers} />
        </Card>
      )}

      {arch && (
        <Card title="Architecture & trust boundaries" icon={<GearSix size={16} />}>
          {arch.summary && <p className="text-sm text-foreground/85">{arch.summary}</p>}
          <div className="mt-3">
            <p className="mb-1 text-xs font-medium text-foreground/60">Components</p>
            <ul className="space-y-1">
              {arch.components.map((c, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <span className="font-medium">{c.name}</span>
                  <span className="text-xs text-foreground/50">{c.role}</span>
                  {c.sensitive && (
                    <span className="rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 text-[10px] uppercase text-warning">
                      sensitive
                    </span>
                  )}
                </li>
              ))}
              {arch.components.length === 0 && <li className="text-sm text-foreground/50">—</li>}
            </ul>
          </div>
          {arch.trust_boundaries.length > 0 && (
            <div className="mt-4">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-warning">
                <WarningCircle size={14} /> Trust boundaries
              </p>
              <ul className="space-y-1.5">
                {arch.trust_boundaries.map((tb, i) => (
                  <li key={i} className="rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-sm">
                    <span className="font-semibold">{tb.between}</span>
                    {tb.reason && <span className="text-xs text-foreground/60"> — {tb.reason}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <LabeledChips label="Data flows" items={arch.data_flows.map((f) => `${f.source} → ${f.destination} (${f.data || 'data'})`)} />
          <LabeledChips label="Entry points" items={arch.entry_points} />
          <LabeledChips label="Integrations" items={arch.integrations} />
        </Card>
      )}

      {assets && (
        <Card title="Assets to protect" icon={<ShieldCheck size={16} />}>
          <ul className="space-y-3">
            {assets.assets.map((a, i) => (
              <li key={i} className="rounded-lg border border-border bg-muted/40 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold">{a.name}</p>
                  <SeverityBadge severity={a.sensitivity} />
                  {a.asset_type && (
                    <span className="rounded-full bg-border/60 px-2 py-0.5 font-mono text-[10px] uppercase text-foreground/60">
                      {a.asset_type}
                    </span>
                  )}
                </div>
                {a.location && <p className="mt-1 text-xs text-foreground/60">Location: {a.location}</p>}
                {a.protection_basis && <p className="mt-1 text-xs text-foreground/70">{a.protection_basis}</p>}
                {a.kb_sources.length > 0 && (
                  <p className="mt-1 font-mono text-[11px] text-foreground/50">basis: {a.kb_sources.join(', ')}</p>
                )}
              </li>
            ))}
            {assets.assets.length === 0 && <p className="text-sm text-foreground/50">—</p>}
          </ul>
        </Card>
      )}

      {threats && (
        <Card title="STRIDE threat model" icon={<WarningCircle size={16} />}>
          {threats.threats.length === 0 ? (
            <p className="text-sm text-foreground/50">No threats identified.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wide text-foreground/50">
                    <th className="py-2 pr-3 font-medium">ID</th>
                    <th className="py-2 pr-3 font-medium">Element</th>
                    <th className="py-2 pr-3 font-medium">STRIDE</th>
                    <th className="py-2 pr-3 font-medium">Scenario</th>
                    <th className="py-2 font-medium">Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {threats.threats.map((t) => (
                    <tr key={t.id} className="border-b border-border align-top last:border-0">
                      <td className="py-2 pr-3 font-mono text-xs text-secondary">{t.id}</td>
                      <td className="py-2 pr-3 font-medium">{t.element}</td>
                      <td className="py-2 pr-3">
                        <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] text-foreground/70">
                          {t.stride_category}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-foreground/80">{t.scenario}</td>
                      <td className="py-2">
                        <SeverityBadge severity={t.severity} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

export function ReviewDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { review, error, loading } = useReview(id)
  const [overriding, setOverriding] = useState(false)
  const [override, setOverride] = useState<Decision | null>(null)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleteMsg, setDeleteMsg] = useState<string | null>(null)

  const agent = review?.llm_decision
  const final = review?.final_decision
  const overridden = useMemo(() => {
    if (!agent || !final) return false
    return (
      agent.test_level !== final.test_level ||
      agent.requires_pentest !== final.requires_pentest
    )
  }, [agent, final])

  const effectiveExposure =
    review?.exposure_override ??
    review?.detected_exposure ??
    (review?.facts?.exposure as string | undefined) ??
    'unclear'

  const effectiveChangeScope =
    review?.change_scope_override ??
    (review?.facts?.change_scope as string | undefined) ??
    'other'

  if (loading && !review) return <p className="text-sm text-foreground/50">Loading review…</p>
  if (error) return <p className="text-sm text-destructive">Failed to load: {error}</p>
  if (!review) return <p className="text-sm text-destructive">Review not found.</p>

  const stageIndex = Math.max(
    0,
    THREAT_STEPS.findIndex((s) => s.key === review.current_stage),
  )

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

  const removeReview = async () => {
    setDeleteMsg(null)
    try {
      await api.deleteReview(review.id)
      navigate('/reviews')
    } catch (err) {
      setDeleteMsg(err instanceof Error ? err.message : String(err))
      setConfirmDelete(false)
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
          <div className="flex items-center gap-2">
            {confirmDelete ? (
              <span className="flex items-center gap-1 rounded-lg border border-border bg-background px-2 py-1 text-xs text-foreground/70">
                Delete this review?
                <button
                  onClick={() => void removeReview()}
                  className="rounded bg-destructive px-2 py-1 text-xs font-semibold text-white hover:opacity-90"
                >
                  Yes
                </button>
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="rounded px-2 py-1 text-xs hover:bg-muted"
                >
                  No
                </button>
              </span>
            ) : (
              <button
                onClick={() => setConfirmDelete(true)}
                className="rounded-lg border border-border p-2 text-foreground/60 hover:bg-destructive/10 hover:text-destructive"
                title="Delete review"
                aria-label="Delete review"
              >
                <Trash size={16} />
              </button>
            )}
          </div>
        </div>
        {deleteMsg && <p className="mt-2 text-xs text-destructive">{deleteMsg}</p>}
      </header>

      {review.status === 'running' && (
        <div className="rounded-xl border border-border bg-background p-8 text-center">
          <Stepper steps={THREAT_STEPS} current={stageIndex} running />
          <p className="mt-6 flex items-center justify-center gap-2 text-sm text-foreground/60">
            <ArrowsClockwise size={16} className="animate-spin" />
            Running local analysis{review.current_stage ? ` · ${review.current_stage}` : ''}… this page
            refreshes automatically.
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

          {review.analysis && (
            <div className="space-y-6">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-foreground/50">
                <ArrowsClockwise size={13} /> Threat-model analysis
              </div>
              <ThreatStages analysis={review.analysis} />
            </div>
          )}

          {review.conflicts.length > 0 && (
            <div className="rounded-xl border border-warning/40 bg-warning/10 p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-warning">
                <WarningCircle size={18} weight="fill" />
                Agent recommendation violates a rule bound
              </h3>
              <ul className="mt-2 space-y-1 text-sm">
                {review.conflicts.map((c, i) => (
                  <li key={i}>
                    <span className="font-mono text-xs text-warning/80">{c.field}:</span> {c.explanation}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <Card title="App exposure" icon={<Globe size={16} />}>
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm">
                  <strong>{EXPOSURE_LABELS[effectiveExposure] ?? effectiveExposure ?? '—'}</strong>
                  {review.exposure_override && (
                    <span className="ml-2 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] uppercase text-primary">
                      override
                    </span>
                  )}
                  {!review.exposure_override && review.detected_exposure && (
                    <span className="ml-2 rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-[10px] uppercase text-accent">
                      from PDF form
                    </span>
                  )}
                  {!review.exposure_override && !review.detected_exposure && (
                    <span className="ml-2 rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] uppercase text-foreground/60">
                      from LLM
                    </span>
                  )}
                </p>
                <p className="mt-0.5 text-xs text-foreground/50">
                  Drives the intranet (DAST-only) vs internet-facing rules.
                </p>
              </div>
              <select
                value={effectiveExposure}
                onChange={async (e) => {
                  const v = e.target.value
                  try {
                    await api.updateExposure(review.id, v === 'unclear' ? null : v)
                  } catch (err) {
                    setSaveMsg(err instanceof Error ? err.message : String(err))
                  }
                }}
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
                aria-label="Confirm app exposure"
              >
                <option value="internal">Intranet</option>
                <option value="internet-facing">Internet-facing</option>
                <option value="partner">Partner / External</option>
                <option value="unclear">Unclear — confirm</option>
              </select>
            </div>
            {effectiveExposure === 'unclear' && (
              <p className="mt-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
                Exposure could not be determined from the documents. Confirm it above so the intranet /
                internet-facing rules fire correctly.
              </p>
            )}
          </Card>

          <Card title="Change scope" icon={<ArrowsClockwise size={16} />}>
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm">
                  <strong>{CHANGE_SCOPE_LABELS[effectiveChangeScope] ?? effectiveChangeScope ?? '—'}</strong>
                  {effectiveChangeScope === 'limited_change' && (
                    <span className="ml-2 rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-[10px] uppercase text-accent">
                      scoped to change
                    </span>
                  )}
                  {review.change_scope_override && (
                    <span className="ml-2 rounded-full border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] uppercase text-primary">
                      override
                    </span>
                  )}
                </p>
                <p className="mt-0.5 text-xs text-foreground/50">
                  Changing this re-runs the review reasoning (DAST vs pentest).
                </p>
              </div>
              <select
                value={effectiveChangeScope}
                onChange={async (e) => {
                  const v = e.target.value
                  try {
                    await api.updateChangeScope(review.id, v === 'auto' ? null : v)
                  } catch (err) {
                    setSaveMsg(err instanceof Error ? err.message : String(err))
                  }
                }}
                className="rounded-lg border border-border bg-background px-3 py-2 text-sm"
                aria-label="Change scope"
              >
                <option value="auto">Auto-detect</option>
                <option value="limited_change">Limited change (no logic impact)</option>
                <option value="feature_change">Feature change</option>
                <option value="full_new_app">New application</option>
                <option value="other">Other</option>
              </select>
            </div>
          </Card>

          <Card title="Reasoning" icon={<FileText size={16} />}>
            <p className="text-sm leading-relaxed text-foreground/85">
              {final.classification_reason}
            </p>
            {(() => {
              const scope = review.facts?.change_scope as string | undefined
              const evidence = review.facts?.change_scope_evidence as string | undefined
              if (!scope) return null
              return (
                <div className="mt-4 rounded-lg border border-border bg-muted/40 p-3">
                  <p className="text-xs font-medium text-foreground/60">
                    Change scope:{' '}
                    <span className="font-semibold text-foreground">
                      {scope.replace(/_/g, ' ')}
                    </span>
                  </p>
                  {evidence && (
                    <p className="mt-1 text-xs text-foreground/60">
                      <span className="font-mono text-foreground/40">"</span>
                      {evidence}
                      <span className="font-mono text-foreground/40">"</span>
                    </p>
                  )}
                </div>
              )
            })()}
            {final.risk_factors.length > 0 && (
              <div className="mt-4">
                <p className="mb-2 text-xs font-medium text-foreground/60">Risk factors</p>
                <ChipList items={final.risk_factors} />
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

          <Card title="Rules (hard bounds)" icon={<ListChecks size={16} />}>
            {!review.rule_engine_enabled ? (
              <p className="text-sm text-foreground/60">
                The rule engine was <strong>disabled</strong> for this review — no deterministic bounds
                were applied.
              </p>
            ) : review.rules_fired.length === 0 ? (
              <p className="text-sm text-foreground/50">No rules matched.</p>
            ) : (
              <>
                <p className="mb-2 text-xs text-foreground/50">
                  Rule level: <strong>{review.rule_test_level ?? '—'}</strong> (applied to the final
                  decision)
                </p>
                <ul className="space-y-3">
                  {review.rules_fired.map((r) => (
                    <li key={r.id} className="rounded-lg border border-border bg-muted/40 p-3">
                      <p className="text-sm font-semibold">
                        <span className="font-mono text-xs text-secondary">{r.id}</span> · {r.name}
                        <span className="ml-2 rounded-full bg-border/60 px-2 py-0.5 font-mono text-[10px] uppercase text-foreground/60">
                          {r.test_level}
                        </span>
                        {r.cap && (
                          <span className="ml-2 rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 font-mono text-[10px] uppercase text-warning">
                            caps at {r.cap}
                          </span>
                        )}
                      </p>
                      <p className="mt-1 text-xs text-foreground/70">{r.reasoning}</p>
                    </li>
                  ))}
                </ul>
              </>
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

          <Card title="Extracted form selections" icon={<ListChecks size={16} />}>
            {review.form_fields.length === 0 ? (
              <p className="text-sm text-foreground/50">
                No form selections were detected in the uploaded PDFs.
              </p>
            ) : (
              <ul className="space-y-2">
                {review.form_fields.map((f, i) => (
                  <li key={i} className="rounded-lg border border-border bg-muted/40 p-3">
                    <p className="text-sm font-medium">{f.label || '(unnamed field)'}</p>
                    <p className="mt-1 text-xs text-foreground/70">
                      <span className="font-semibold text-accent">
                        Selected: {f.selected.join(', ')}
                      </span>
                      {f.options.length > 0 && (
                        <span className="text-foreground/50"> · options: {f.options.join(' | ')}</span>
                      )}
                    </p>
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
                {(['dast', 'pentest', 'none'] as TestLevel[]).map((level) => (
                  <button
                    key={level}
                    disabled={!overriding}
                    onClick={() =>
                      setOverride((o) => ({
                        ...(o ?? final),
                        test_level: level,
                        requires_pentest: level === 'pentest',
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
