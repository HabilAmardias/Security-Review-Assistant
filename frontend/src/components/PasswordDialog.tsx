import { useState } from 'react'
import { Key, LockSimple } from '@phosphor-icons/react'
import { Modal } from './Modal'

interface Props {
  docName: string
  subtitle?: string
  submitLabel?: string
  busy?: boolean
  onSubmit: (password: string) => Promise<void> | void
  onClose: () => void
}

export function PasswordDialog({
  docName,
  subtitle,
  submitLabel = 'Unlock',
  busy = false,
  onSubmit,
  onClose,
}: Props) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!password) {
      setError('Enter the document password.')
      return
    }
    try {
      await onSubmit(password)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <Modal title="Document is locked" onClose={onClose}>
      <p className="mb-1 text-sm text-foreground/80">
        <LockSimple size={14} className="mr-1 inline" />
        {docName}
      </p>
      {subtitle && <p className="mb-4 text-xs text-foreground/60">{subtitle}</p>}
      <p className="mb-3 text-xs text-foreground/60">
        The password is used only in memory to decrypt the PDF. It is never stored or logged.
      </p>
      <label className="mb-1 block text-xs font-medium" htmlFor="pdf-password">
        PDF password
      </label>
      <div className="relative">
        <Key size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground/50" />
        <input
          id="pdf-password"
          type="password"
          autoFocus
          value={password}
          onChange={(e) => {
            setPassword(e.target.value)
            setError(null)
          }}
          onKeyDown={(e) => e.key === 'Enter' && void submit()}
          className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm focus:border-secondary"
          placeholder="••••••••"
        />
      </div>
      {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
      <div className="mt-5 flex justify-end gap-2">
        <button
          onClick={onClose}
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
        >
          Cancel
        </button>
        <button
          onClick={() => void submit()}
          disabled={busy}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary hover:opacity-90 disabled:opacity-50"
        >
          {busy ? 'Working…' : submitLabel}
        </button>
      </div>
    </Modal>
  )
}
