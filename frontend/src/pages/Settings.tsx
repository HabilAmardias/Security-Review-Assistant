import { useEffect, useState } from 'react'
import { Cpu, Database, FloppyDisk, ArrowCounterClockwise } from '@phosphor-icons/react'
import { api } from '../api/client'
import type { BusinessSettings, Health } from '../types'

const STEPS = ['fact_extraction', 'diagrams', 'requirement', 'architecture', 'assets', 'threats', 'decision']

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex items-center justify-between gap-4 border-b border-border px-5 py-3 last:border-0">
      <span>
        <span className="block text-sm text-foreground/80">{label}</span>
        {hint && <span className="block text-xs text-foreground/45">{hint}</span>}
      </span>
      <span className="shrink-0">{children}</span>
    </label>
  )
}

const inputCls = 'w-40 rounded-lg border border-border bg-background px-3 py-1.5 text-sm'

export function Settings() {
  const [draft, setDraft] = useState<BusinessSettings | null>(null)
  const [models, setModels] = useState<string[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const load = () =>
    Promise.all([api.getSettings(), api.health()])
      .then(([s, h]) => {
        setDraft(s.settings)
        setModels(s.models)
        setHealth(h)
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))

  useEffect(() => {
    void load()
  }, [])

  if (err) return <p className="text-sm text-destructive">{err}</p>
  if (!draft) return <p className="text-sm text-foreground/50">Loading settings…</p>

  const setLlm = (patch: Partial<BusinessSettings['llm']>) => setDraft({ ...draft, llm: { ...draft.llm, ...patch } })
  const setExtraction = (patch: Partial<BusinessSettings['extraction']>) =>
    setDraft({ ...draft, extraction: { ...draft.extraction, ...patch } })
  const setRetrieval = (patch: Partial<BusinessSettings['retrieval']>) =>
    setDraft({ ...draft, retrieval: { ...draft.retrieval, ...patch } })

  const save = async () => {
    setSaving(true)
    setMsg(null)
    setErr(null)
    try {
      const res = await api.updateSettings(draft)
      setDraft(res.settings)
      setMsg(res.reindex_required ? 'Saved. Re-indexing the knowledge base with the new embedding model…' : 'Settings saved.')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  const reset = async () => {
    setSaving(true)
    setMsg(null)
    try {
      const res = await api.resetSettings()
      setDraft(res.settings)
      setMsg('Reset to defaults.')
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  const modelOptions = (current: string) => {
    const list = models.includes(current) || !current ? models : [current, ...models]
    return list.map((m) => (
      <option key={m} value={m}>
        {m}
      </option>
    ))
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-16">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="mt-1 text-sm text-foreground/60">
            Business-logic configuration. Infrastructure (Ollama URL, data dir, host/port) lives in{' '}
            <code className="font-mono">backend/.env</code>.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => void reset()}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            <ArrowCounterClockwise size={16} /> Reset
          </button>
          <button
            onClick={() => void save()}
            disabled={saving}
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-50"
          >
            <FloppyDisk size={16} /> {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </header>

      {msg && <p className="rounded-lg border border-accent/40 bg-accent/10 px-4 py-3 text-sm text-accent">{msg}</p>}
      {err && <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">{err}</p>}

      <section className="overflow-hidden rounded-xl border border-border bg-background">
        <h2 className="flex items-center gap-2 border-b border-border px-5 py-3 text-sm font-semibold uppercase tracking-wide text-foreground/60">
          <Cpu size={16} /> Models
        </h2>
        <Field label="Reasoning model" hint="Used for fact extraction and all review stages.">
          <select value={draft.llm.reasoning_model} onChange={(e) => setLlm({ reasoning_model: e.target.value })} className={inputCls}>
            {modelOptions(draft.llm.reasoning_model)}
          </select>
        </Field>
        <Field label="Embedding model" hint="Changing this re-indexes the knowledge base.">
          <select value={draft.llm.embedding_model} onChange={(e) => setLlm({ embedding_model: e.target.value })} className={inputCls}>
            {modelOptions(draft.llm.embedding_model)}
          </select>
        </Field>
        <Field label="Embedding dimension" hint="Auto-detected on save when the model changes.">
          <input
            type="number"
            value={draft.llm.embedding_dim}
            onChange={(e) => setLlm({ embedding_dim: Number(e.target.value) })}
            className={inputCls}
          />
        </Field>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-background">
        <h2 className="border-b border-border px-5 py-3 text-sm font-semibold uppercase tracking-wide text-foreground/60">
          Generation
        </h2>
        <Field label="Temperature">
          <input type="number" step="0.1" value={draft.llm.temperature} onChange={(e) => setLlm({ temperature: Number(e.target.value) })} className={inputCls} />
        </Field>
        <Field label="Max tokens (output)">
          <input type="number" value={draft.llm.max_tokens} onChange={(e) => setLlm({ max_tokens: Number(e.target.value) })} className={inputCls} />
        </Field>
        <Field label="Context window (num_ctx)">
          <input type="number" value={draft.llm.num_ctx} onChange={(e) => setLlm({ num_ctx: Number(e.target.value) })} className={inputCls} />
        </Field>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-background">
        <h2 className="border-b border-border px-5 py-3 text-sm font-semibold uppercase tracking-wide text-foreground/60">
          Thinking per step
        </h2>
        {STEPS.map((step) => (
          <Field key={step} label={step.replace(/_/g, ' ')}>
            <input
              type="checkbox"
              checked={draft.llm.thinking[step] ?? false}
              onChange={(e) => setLlm({ thinking: { ...draft.llm.thinking, [step]: e.target.checked } })}
              className="h-4 w-4 accent-primary"
            />
          </Field>
        ))}
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-background">
        <h2 className="border-b border-border px-5 py-3 text-sm font-semibold uppercase tracking-wide text-foreground/60">
          Extraction & diagrams
        </h2>
        <Field label="Default extraction mode">
          <select value={draft.extraction.default_mode} onChange={(e) => setExtraction({ default_mode: e.target.value })} className={inputCls}>
            <option value="auto">Auto</option>
            <option value="text">Text layer</option>
            <option value="ocr">Force OCR</option>
          </select>
        </Field>
        <Field label="OCR flag threshold (chars/page)">
          <input type="number" value={draft.extraction.auto_detect_threshold} onChange={(e) => setExtraction({ auto_detect_threshold: Number(e.target.value) })} className={inputCls} />
        </Field>
        <Field label="OCR language">
          <input value={draft.extraction.ocr_language} onChange={(e) => setExtraction({ ocr_language: e.target.value })} className={inputCls} />
        </Field>
        <Field label="Diagram DPI">
          <input type="number" value={draft.extraction.diagram_dpi} onChange={(e) => setExtraction({ diagram_dpi: Number(e.target.value) })} className={inputCls} />
        </Field>
        <Field label="Max diagram pages">
          <input type="number" value={draft.extraction.max_diagram_pages} onChange={(e) => setExtraction({ max_diagram_pages: Number(e.target.value) })} className={inputCls} />
        </Field>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-background">
        <h2 className="border-b border-border px-5 py-3 text-sm font-semibold uppercase tracking-wide text-foreground/60">
          Retrieval & chunking
        </h2>
        <Field label="Chunk size">
          <input type="number" value={draft.retrieval.chunk_size} onChange={(e) => setRetrieval({ chunk_size: Number(e.target.value) })} className={inputCls} />
        </Field>
        <Field label="Chunk overlap">
          <input type="number" value={draft.retrieval.chunk_overlap} onChange={(e) => setRetrieval({ chunk_overlap: Number(e.target.value) })} className={inputCls} />
        </Field>
        <Field label="Embedding batch size">
          <input type="number" value={draft.retrieval.embed_batch_size} onChange={(e) => setRetrieval({ embed_batch_size: Number(e.target.value) })} className={inputCls} />
        </Field>
        <Field label="Retrieval top-k">
          <input type="number" value={draft.retrieval.retrieval_top_k} onChange={(e) => setRetrieval({ retrieval_top_k: Number(e.target.value) })} className={inputCls} />
        </Field>
        <Field label="Review max input chars">
          <input type="number" value={draft.retrieval.review_max_input_chars} onChange={(e) => setRetrieval({ review_max_input_chars: Number(e.target.value) })} className={inputCls} />
        </Field>
        <Field label="Enable rule engine" hint="Intranet DAST cap / internet DAST floor as hard bounds.">
          <input
            type="checkbox"
            checked={draft.retrieval.enable_rule_engine}
            onChange={(e) => setRetrieval({ enable_rule_engine: e.target.checked })}
            className="h-4 w-4 accent-primary"
          />
        </Field>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-background">
        <h2 className="flex items-center gap-2 border-b border-border px-5 py-3 text-sm font-semibold uppercase tracking-wide text-foreground/60">
          <Database size={16} /> Runtime
        </h2>
        <Field label="Ollama">
          {health?.ollama ? <span className="text-sm text-accent">connected</span> : <span className="text-sm text-destructive">offline</span>}
        </Field>
        <Field label="Documents indexed">
          <span className="text-sm">{health?.documents_indexed ?? '—'}</span>
        </Field>
        <Field label="Storage">
          <code className="font-mono text-xs">data/app.db · data/chroma · data/documents</code>
        </Field>
      </section>

      <p className="text-xs text-foreground/50">
        Rule definitions (R-06/R-11) are read from <code className="font-mono">backend/config/compliance.yaml</code>.
      </p>
    </div>
  )
}
