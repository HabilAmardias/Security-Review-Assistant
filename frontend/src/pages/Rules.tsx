import { useEffect, useState } from 'react'
import { PencilSimple, Plus, Trash } from '@phosphor-icons/react'
import { api } from '../api/client'
import { Modal } from '../components/Modal'
import type { Rule } from '../types'

const LEVELS = ['pentest', 'dast', 'none']
const PRIORITIES = ['high', 'medium', 'low']

function emptyRule(): Rule {
  return {
    id: '',
    name: '',
    enabled: true,
    triggers: { data_classes: [], keywords: [], features: [], exposure: [] },
    action: { test_level: 'dast', priority: 'medium', cap: null },
    reasoning: '',
  }
}

function parseList(value: string): string[] {
  return value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

const inputCls = 'w-full rounded-lg border border-border bg-background px-3 py-2 text-sm'

function TriggerField({
  label,
  value,
  onChange,
}: {
  label: string
  value: string[]
  onChange: (v: string[]) => void
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-foreground/60">{label} (comma-separated)</label>
      <input
        value={value.join(', ')}
        onChange={(e) => onChange(parseList(e.target.value))}
        className={inputCls}
      />
    </div>
  )
}

export function Rules() {
  const [rules, setRules] = useState<Rule[]>([])
  const [editing, setEditing] = useState<Rule | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = () => api.rules().then(setRules).catch((e) => setErr(String(e)))
  useEffect(() => {
    void load()
  }, [])

  const save = async () => {
    if (!editing) return
    setBusy(true)
    setErr(null)
    try {
      if (isNew) await api.createRule(editing)
      else await api.updateRule(editing.id, editing)
      setEditing(null)
      setMsg('Saved. Applies to the next review.')
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const toggle = async (rule: Rule) => {
    try {
      await api.patchRule(rule.id, { enabled: !rule.enabled })
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const remove = async (id: string) => {
    try {
      await api.deleteRule(id)
      setConfirmId(null)
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  const reset = async () => {
    try {
      await api.resetRules()
      setMsg('Rules reset to defaults.')
      await load()
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Rules</h1>
          <p className="mt-1 text-sm text-foreground/60">
            Deterministic rules that act as hard bounds on the review verdict. Changes apply to the next review.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => void reset()}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            Reset to defaults
          </button>
          <button
            onClick={() => {
              setEditing(emptyRule())
              setIsNew(true)
            }}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90"
          >
            <Plus size={16} /> Add rule
          </button>
        </div>
      </header>

      {msg && <p className="mb-4 rounded-lg border border-accent/40 bg-accent/10 px-4 py-2 text-sm text-accent">{msg}</p>}
      {err && <p className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive">{err}</p>}

      {rules.length === 0 && <p className="text-sm text-foreground/50">No rules. Add one or reset to defaults.</p>}

      <ul className="space-y-3">
        {rules.map((r) => (
          <li
            key={r.id}
            className={`rounded-xl border border-border bg-background p-4 ${r.enabled ? '' : 'opacity-60'}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold">
                  <span className="font-mono text-xs text-secondary">{r.id}</span> · {r.name}
                  <span className="ml-2 rounded-full border border-border bg-muted px-2 py-0.5 font-mono text-[10px] uppercase text-foreground/60">
                    {r.action.test_level}
                  </span>
                  {r.action.cap && (
                    <span className="ml-2 rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 font-mono text-[10px] uppercase text-warning">
                      caps at {r.action.cap}
                    </span>
                  )}
                  <span className="ml-2 rounded-full border border-border bg-muted px-2 py-0.5 font-mono text-[10px] uppercase text-foreground/60">
                    {r.action.priority}
                  </span>
                </p>
                <p className="mt-1 text-xs text-foreground/60">{r.reasoning}</p>
                <p className="mt-1 font-mono text-[11px] text-foreground/40">
                  triggers: {[
                    r.triggers.exposure.length ? `exposure=${r.triggers.exposure.join('|')}` : '',
                    r.triggers.data_classes.length ? `data=${r.triggers.data_classes.join('|')}` : '',
                    r.triggers.features.length ? `features=${r.triggers.features.join('|')}` : '',
                    r.triggers.keywords.length ? `keywords=${r.triggers.keywords.join('|')}` : '',
                  ]
                    .filter(Boolean)
                    .join('  ')}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <label className="flex items-center gap-1 text-xs text-foreground/60">
                  <input
                    type="checkbox"
                    checked={r.enabled}
                    onChange={() => void toggle(r)}
                    className="h-4 w-4 accent-primary"
                  />
                  enabled
                </label>
                <button
                  onClick={() => {
                    setEditing(structuredClone(r))
                    setIsNew(false)
                  }}
                  className="rounded-lg border border-border p-2 hover:bg-muted"
                  aria-label={`Edit ${r.id}`}
                >
                  <PencilSimple size={15} />
                </button>
                {confirmId === r.id ? (
                  <span className="flex items-center gap-1 text-xs">
                    <button onClick={() => void remove(r.id)} className="rounded bg-destructive px-2 py-1 text-white">
                      Delete
                    </button>
                    <button onClick={() => setConfirmId(null)} className="rounded px-2 py-1 hover:bg-muted">
                      No
                    </button>
                  </span>
                ) : (
                  <button
                    onClick={() => setConfirmId(r.id)}
                    className="rounded-lg border border-border p-2 text-foreground/60 hover:bg-destructive/10 hover:text-destructive"
                    aria-label={`Delete ${r.id}`}
                  >
                    <Trash size={15} />
                  </button>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>

      {editing && (
        <Modal title={isNew ? 'Add rule' : `Edit ${editing.id}`} onClose={() => setEditing(null)}>
          <div className="max-h-[70vh] space-y-3 overflow-y-auto">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground/60">ID</label>
                <input
                  value={editing.id}
                  disabled={!isNew}
                  onChange={(e) => setEditing({ ...editing, id: e.target.value })}
                  className={inputCls}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground/60">Priority</label>
                <select
                  value={editing.action.priority}
                  onChange={(e) => setEditing({ ...editing, action: { ...editing.action, priority: e.target.value } })}
                  className={inputCls}
                >
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground/60">Name</label>
              <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} className={inputCls} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground/60">Test level</label>
                <select
                  value={editing.action.test_level}
                  onChange={(e) => setEditing({ ...editing, action: { ...editing.action, test_level: e.target.value as Rule['action']['test_level'] } })}
                  className={inputCls}
                >
                  {LEVELS.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground/60">Cap (upper bound)</label>
                <select
                  value={editing.action.cap ?? ''}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      action: { ...editing.action, cap: (e.target.value || null) as Rule['action']['cap'] },
                    })
                  }
                  className={inputCls}
                >
                  <option value="">none</option>
                  {LEVELS.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <TriggerField
              label="Exposure"
              value={editing.triggers.exposure}
              onChange={(v) => setEditing({ ...editing, triggers: { ...editing.triggers, exposure: v } })}
            />
            <TriggerField
              label="Data classes"
              value={editing.triggers.data_classes}
              onChange={(v) => setEditing({ ...editing, triggers: { ...editing.triggers, data_classes: v } })}
            />
            <TriggerField
              label="Features"
              value={editing.triggers.features}
              onChange={(v) => setEditing({ ...editing, triggers: { ...editing.triggers, features: v } })}
            />
            <TriggerField
              label="Keywords"
              value={editing.triggers.keywords}
              onChange={(v) => setEditing({ ...editing, triggers: { ...editing.triggers, keywords: v } })}
            />
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground/60">Reasoning</label>
              <textarea
                rows={3}
                value={editing.reasoning}
                onChange={(e) => setEditing({ ...editing, reasoning: e.target.value })}
                className={inputCls}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={editing.enabled}
                onChange={(e) => setEditing({ ...editing, enabled: e.target.checked })}
                className="h-4 w-4 accent-primary"
              />
              Enabled
            </label>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <button onClick={() => setEditing(null)} className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted">
              Cancel
            </button>
            <button
              onClick={() => void save()}
              disabled={busy || !editing.id || !editing.name}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-50"
            >
              {busy ? 'Saving…' : 'Save'}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
