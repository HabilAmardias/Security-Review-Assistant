import { useMemo, useState } from 'react'
import {
  ArrowsClockwise,
  FilePdf,
  LockSimple,
  Scan,
  Trash,
} from '@phosphor-icons/react'
import { api } from '../api/client'
import { Dropzone } from '../components/Dropzone'
import { PasswordDialog } from '../components/PasswordDialog'
import { StatusBadge } from '../components/StatusBadge'
import { useDocuments } from '../hooks/useDocuments'
import type { DocType, Document } from '../types'

const TYPE_META: Record<DocType, { label: string; hint: string }> = {
  sop: { label: 'SOP', hint: 'Standard operating procedures' },
  policy: { label: 'Policy', hint: 'Security policies' },
  previous: { label: 'Previous reviews', hint: 'Past security review reports (precedent)' },
}

export function KnowledgeBase() {
  const { docs, error, loading } = useDocuments()
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [unlockTarget, setUnlockTarget] = useState<Document | null>(null)
  const [ocrTarget, setOcrTarget] = useState<Document | null>(null)
  const [upload, setUpload] = useState<{ file: File; docType: DocType; mode: string; password: string } | null>(null)

  const grouped = useMemo(() => {
    const g: Record<string, Document[]> = { sop: [], policy: [], previous: [] }
    for (const d of docs) g[d.doc_type]?.push(d)
    return g
  }, [docs])

  const doUpload = async (file: File, docType: DocType, mode: string, password: string) => {
    setBusy(true)
    setNotice(null)
    try {
      const doc = await api.uploadDocument(file, docType, mode, password || undefined)
      if (doc.is_locked || doc.status === 'needs_password') {
        setUnlockTarget(doc)
      }
      setUpload(null)
    } catch (err) {
      setNotice(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const rescan = async () => {
    setBusy(true)
    try {
      const r = await api.rescan()
      setNotice(`Drop folder scanned — ${r.enqueued} new/changed file(s) enqueued.`)
    } catch (err) {
      setNotice(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const reindex = async () => {
    setBusy(true)
    setNotice(null)
    try {
      await api.reindexAll()
      setNotice('Index rebuild started — documents are being re-embedded with the current model.')
    } catch (err) {
      setNotice(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Knowledge Base</h1>
          <p className="mt-1 text-sm text-foreground/60">
            SOP, policies, and previous security reviews the agent uses to decide pentest vs DAST.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => void reindex()}
            disabled={busy}
            title="Use after changing the embedding model"
            className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            <ArrowsClockwise size={16} className={busy ? 'animate-spin' : ''} />
            Rebuild index
          </button>
          <button
            onClick={() => void rescan()}
            disabled={busy}
            className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted disabled:opacity-50"
          >
            <ArrowsClockwise size={16} className={busy ? 'animate-spin' : ''} />
            Scan drop folder
          </button>
        </div>
      </header>

      {notice && (
        <div className="mb-6 rounded-lg border border-accent/40 bg-accent/10 px-4 py-3 text-sm text-accent">
          {notice}
        </div>
      )}

      {/* Upload */}
      <section className="mb-8 rounded-xl border border-border bg-background p-6">
        <h2 className="mb-4 text-base font-semibold">Upload a document</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Dropzone
            label="Choose a PDF to add to the knowledge base"
            onFile={(f) => setUpload((u) => ({ file: f, docType: u?.docType ?? 'sop', mode: u?.mode ?? 'auto', password: u?.password ?? '' }))}
          />
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-3 gap-2">
              {(Object.keys(TYPE_META) as DocType[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setUpload((u) => ({ file: u?.file ?? upload?.file ?? ({} as File), docType: t, mode: u?.mode ?? 'auto', password: u?.password ?? '' }))}
                  className={`rounded-lg border px-2 py-2 text-left text-sm transition-colors ${
                    upload?.docType === t
                      ? 'border-primary bg-primary/5 font-semibold'
                      : 'border-border hover:border-primary/40'
                  }`}
                >
                  {TYPE_META[t].label}
                  <span className="block text-[10px] font-normal text-foreground/50">
                    {TYPE_META[t].hint}
                  </span>
                </button>
              ))}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium">Extraction mode</label>
              <select
                value={upload?.mode ?? 'auto'}
                onChange={(e) => setUpload((u) => ({ file: u?.file ?? ({} as File), docType: u?.docType ?? 'sop', mode: e.target.value, password: u?.password ?? '' }))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="auto">Auto (detect scanned docs)</option>
                <option value="text">Text layer only</option>
                <option value="ocr">Force OCR</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium">
                Password <span className="text-foreground/40">(if locked — never stored)</span>
              </label>
              <input
                type="password"
                value={upload?.password ?? ''}
                onChange={(e) => setUpload((u) => ({ file: u?.file ?? ({} as File), docType: u?.docType ?? 'sop', mode: u?.mode ?? 'auto', password: e.target.value }))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                placeholder="Optional"
              />
            </div>
            <button
              onClick={() => upload && void doUpload(upload.file, upload.docType, upload.mode, upload.password)}
              disabled={!upload?.file || busy}
              className="mt-1 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-40"
            >
              Upload & index
            </button>
          </div>
        </div>
      </section>

      {/* Documents */}
      <section>
        {loading && <p className="text-sm text-foreground/50">Loading documents…</p>}
        {error && <p className="text-sm text-destructive">Failed to load: {error}</p>}
        {(Object.keys(TYPE_META) as DocType[]).map((t) => (
          <div key={t} className="mb-8">
            <div className="mb-2 flex items-center gap-2">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-foreground/60">
                {TYPE_META[t].label}
              </h2>
              <span className="rounded-full bg-muted px-2 py-0.5 font-mono text-xs text-foreground/50">
                {grouped[t].length}
              </span>
            </div>
            {grouped[t].length === 0 ? (
              <p className="rounded-lg border border-dashed border-border px-4 py-4 text-xs text-foreground/40">
                No documents yet. Drop PDFs into <code className="font-mono">data/dropbox/{t}/</code> or upload above.
              </p>
            ) : (
              <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-background">
                {grouped[t].map((d) => (
                  <li key={d.id} className="flex items-center gap-3 px-4 py-3">
                    <FilePdf size={20} className="shrink-0 text-destructive" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{d.name}</p>
                      <p className="font-mono text-xs text-foreground/50">
                        {d.pages ? `${d.pages} pages` : ''}
                        {d.chunk_count ? ` · ${d.chunk_count} chunks` : ''}
                        {d.extraction_mode ? ` · ${d.extraction_mode}` : ''}
                      </p>
                      {d.error && <p className="mt-0.5 text-xs text-destructive">{d.error}</p>}
                    </div>
                    <StatusBadge status={d.status} />
                    <div className="flex items-center gap-1">
                      {(d.status === 'needs_password' || (d.is_locked && d.status !== 'ready')) && (
                        <button
                          onClick={() => setUnlockTarget(d)}
                          className="rounded-lg border border-border p-2 text-sm hover:bg-muted"
                          title="Unlock with password"
                          aria-label={`Unlock ${d.name}`}
                        >
                          <LockSimple size={16} />
                        </button>
                      )}
                      {d.status === 'needs_ocr' && (
                        <button
                          onClick={() => setOcrTarget(d)}
                          className="flex items-center gap-1 rounded-lg border border-border px-2 py-2 text-sm hover:bg-muted"
                          title="Run OCR"
                        >
                          <Scan size={16} />
                        </button>
                      )}
                      <button
                        onClick={() => void api.deleteDocument(d.id)}
                        className="rounded-lg border border-border p-2 text-sm text-foreground/60 hover:bg-destructive/10 hover:text-destructive"
                        title="Delete"
                        aria-label={`Delete ${d.name}`}
                      >
                        <Trash size={16} />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </section>

      {unlockTarget && (
        <PasswordDialog
          docName={unlockTarget.name}
          subtitle="Enter the password to index this PDF."
          onSubmit={async (pw) => {
            await api.unlockDocument(unlockTarget.id, pw)
            setUnlockTarget(null)
          }}
          onClose={() => setUnlockTarget(null)}
        />
      )}
      {ocrTarget && (
        <PasswordDialog
          docName={ocrTarget.name}
          subtitle="Run OCR on this scanned document."
          submitLabel={ocrTarget.is_locked ? 'Unlock & run OCR' : 'Run OCR'}
          onSubmit={async (pw) => {
            await api.runOcr(ocrTarget.id, ocrTarget.is_locked ? pw : undefined)
            setOcrTarget(null)
          }}
          onClose={() => setOcrTarget(null)}
        />
      )}
    </div>
  )
}
