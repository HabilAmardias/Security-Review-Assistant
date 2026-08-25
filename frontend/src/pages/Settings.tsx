import { useEffect, useState } from 'react'
import { Cpu, Database } from '@phosphor-icons/react'
import { api } from '../api/client'
import type { Health, ModelsInfo } from '../types'

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-border px-5 py-3 last:border-0">
      <span className="text-sm text-foreground/60">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  )
}

export function Settings() {
  const [health, setHealth] = useState<Health | null>(null)
  const [models, setModels] = useState<ModelsInfo | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.health(), api.models()])
      .then(([h, m]) => {
        setHealth(h)
        setModels(m)
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
  }, [])

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="mt-1 text-sm text-foreground/60">
          Models are configured in <code className="font-mono">backend/config/config.yaml</code>.
          Restart the backend after editing.
        </p>
      </header>

      {err && <p className="text-sm text-destructive">{err}</p>}

      <section className="overflow-hidden rounded-xl border border-border bg-background">
        <h2 className="flex items-center gap-2 border-b border-border px-5 py-3 text-sm font-semibold uppercase tracking-wide text-foreground/60">
          <Cpu size={16} />
          Local engine
        </h2>
        <Row label="Ollama" value={health?.ollama ? <span className="text-accent">connected</span> : <span className="text-destructive">offline</span>} />
        <Row label="Reasoning model" value={models?.reasoning_model ?? '—'} />
        <Row label="Embedding model" value={models?.embedding_model ?? '—'} />
        <Row label="Documents indexed" value={health?.documents_indexed ?? '—'} />
        <div className="px-5 py-3">
          <p className="mb-2 text-sm text-foreground/60">Available models on this machine</p>
          <div className="flex flex-wrap gap-2">
            {(models?.available ?? []).map((m) => (
              <span key={m} className="rounded-full border border-border bg-muted px-3 py-1 font-mono text-xs">
                {m}
              </span>
            ))}
            {models && models.available.length === 0 && (
              <span className="text-xs text-foreground/50">No models pulled yet. Run <code className="font-mono">ollama pull &lt;model&gt;</code></span>
            )}
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-border bg-background">
        <h2 className="flex items-center gap-2 border-b border-border px-5 py-3 text-sm font-semibold uppercase tracking-wide text-foreground/60">
          <Database size={16} />
          Storage
        </h2>
        <Row label="SQLite metadata / audit log" value={<code className="font-mono text-xs">data/app.db</code>} />
        <Row label="Vector index" value={<code className="font-mono text-xs">data/chroma</code>} />
        <Row label="Plaintext cache" value={<code className="font-mono text-xs">data/extracted</code>} />
        <Row label="Drop folder" value={<code className="font-mono text-xs">{'data/dropbox/{sop,policy,previous}'}</code>} />
      </section>

      <p className="text-xs text-foreground/50">
        Passwords entered for locked PDFs are used in memory only during decryption and are never
        stored in the database or logs.
      </p>
    </div>
  )
}
