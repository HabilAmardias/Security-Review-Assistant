import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play } from '@phosphor-icons/react'
import { api } from '../api/client'
import { Dropzone } from '../components/Dropzone'
import { PasswordDialog } from '../components/PasswordDialog'
import type { Review } from '../types'

export function NewReview() {
  const navigate = useNavigate()
  const [frd, setFrd] = useState<File | null>(null)
  const [nfrd, setNfrd] = useState<File | null>(null)
  const [frdPw, setFrdPw] = useState('')
  const [nfrdPw, setNfrdPw] = useState('')
  const [exposure, setExposure] = useState('auto')
  const [changeScope, setChangeScope] = useState('auto')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lockedTarget, setLockedTarget] = useState<{ which: 'frd' | 'nfrd' } | null>(null)

  const submit = async (pwFrd = frdPw, pwNfrd = nfrdPw) => {
    if (!frd || !nfrd) {
      setError('Both FRD and NFRD documents are required.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const review: Review = await api.createReview(
        frd,
        nfrd,
        pwFrd || undefined,
        pwNfrd || undefined,
        exposure,
        changeScope,
      )
      navigate(`/reviews/${review.id}`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      // Distinguish password-needed errors from the backend
      if (/password|decrypted/i.test(msg)) {
        const which = /FRD|frd/i.test(msg) ? 'frd' : 'nfrd'
        setLockedTarget({ which })
      }
      setError(msg)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">New Security Review</h1>
        <p className="mt-1 text-sm text-foreground/60">
          Upload the FRD and NFRD. The agent will extract facts, apply your SOP/policy rules,
          consult previous reviews, and recommend pentest vs DAST with scope.
        </p>
      </header>

      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <label className="mb-2 block text-sm font-semibold">Functional Requirements (FRD)</label>
          <Dropzone
            label="Drop FRD here"
            accept=".pdf,.md,.markdown,.txt"
            hint="PDF, Markdown, or TXT · click to browse or drop"
            onFile={setFrd}
          />
          <div className="mt-2">
            <label className="mb-1 block text-xs font-medium text-foreground/60">
              Password <span className="font-normal">(locked PDF only)</span>
            </label>
            <input
              type="password"
              value={frdPw}
              onChange={(e) => setFrdPw(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              placeholder="Optional"
            />
          </div>
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold">Non-Functional Requirements (NFRD)</label>
          <Dropzone
            label="Drop NFRD here"
            accept=".pdf,.md,.markdown,.txt"
            hint="PDF, Markdown, or TXT · click to browse or drop"
            onFile={setNfrd}
          />
          <div className="mt-2">
            <label className="mb-1 block text-xs font-medium text-foreground/60">
              Password <span className="font-normal">(locked PDF only)</span>
            </label>
            <input
              type="password"
              value={nfrdPw}
              onChange={(e) => setNfrdPw(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              placeholder="Optional"
            />
          </div>
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

      <div className="mt-6 rounded-xl border border-border bg-background p-4">
        <label className="mb-1 block text-sm font-medium">App exposure</label>
        <p className="mb-2 text-xs text-foreground/50">
          The pipeline auto-detects this from the PDF form. Choose explicitly to override or when
          the document doesn't encode it.
        </p>
        <div className="flex flex-wrap gap-2">
          {(
            [
              ['auto', 'Auto-detect'],
              ['internal', 'Intranet'],
              ['internet-facing', 'Internet-facing'],
              ['partner', 'Partner / External'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setExposure(value)}
              className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                exposure === value
                  ? 'border-primary bg-primary/10 font-semibold text-primary'
                  : 'border-border hover:border-primary/40'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-border bg-background p-4">
        <label className="mb-1 block text-sm font-medium">Change scope</label>
        <p className="mb-2 text-xs text-foreground/50">
          Auto-detected from the FRD. A limited change (no business-logic/data impact) is taken into
          account by the review reasoning.
        </p>
        <div className="flex flex-wrap gap-2">
          {(
            [
              ['auto', 'Auto-detect'],
              ['limited_change', 'Limited change (no logic impact)'],
              ['feature_change', 'Feature change'],
              ['full_new_app', 'New application'],
              ['other', 'Other'],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setChangeScope(value)}
              className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                changeScope === value
                  ? 'border-primary bg-primary/10 font-semibold text-primary'
                  : 'border-border hover:border-primary/40'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 flex justify-end">
        <button
          onClick={() => void submit()}
          disabled={busy}
          className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-50"
        >
          <Play size={16} weight="fill" />
          {busy ? 'Submitting…' : 'Run review'}
        </button>
      </div>

      <p className="mt-8 text-xs text-foreground/50">
        Reviews run fully on-premise via local Ollama. Passwords are used in memory only and never
        stored.
      </p>

      {lockedTarget && (
        <PasswordDialog
          docName={lockedTarget.which === 'frd' ? 'FRD' : 'NFRD'}
          subtitle="This document appears to be password-protected."
          submitLabel="Unlock & run review"
          onSubmit={async (pw) => {
            setLockedTarget(null)
            if (lockedTarget.which === 'frd') {
              await submit(pw, nfrdPw)
            } else {
              await submit(frdPw, pw)
            }
          }}
          onClose={() => setLockedTarget(null)}
        />
      )}
    </div>
  )
}
