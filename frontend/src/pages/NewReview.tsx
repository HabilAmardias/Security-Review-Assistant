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
      const review: Review = await api.createReview(frd, nfrd, pwFrd || undefined, pwNfrd || undefined)
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
          <Dropzone label="Drop FRD here" onFile={setFrd} />
          <div className="mt-2">
            <label className="mb-1 block text-xs font-medium text-foreground/60">
              Password <span className="font-normal">(if locked)</span>
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
          <Dropzone label="Drop NFRD here" onFile={setNfrd} />
          <div className="mt-2">
            <label className="mb-1 block text-xs font-medium text-foreground/60">
              Password <span className="font-normal">(if locked)</span>
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
