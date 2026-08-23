import type { DocStatus } from '../types'

const STYLES: Record<DocStatus, { label: string; cls: string; pulse?: boolean }> = {
  pending: { label: 'Pending', cls: 'bg-muted text-foreground/70 border-border' },
  needs_password: { label: 'Needs password', cls: 'bg-warning/10 text-warning border-warning/30' },
  needs_ocr: { label: 'Needs OCR', cls: 'bg-warning/10 text-warning border-warning/30' },
  extracting: { label: 'Extracting…', cls: 'bg-secondary/10 text-secondary border-secondary/30', pulse: true },
  chunking: { label: 'Chunking…', cls: 'bg-secondary/10 text-secondary border-secondary/30', pulse: true },
  embedding: { label: 'Embedding…', cls: 'bg-secondary/10 text-secondary border-secondary/30', pulse: true },
  ready: { label: 'Ready', cls: 'bg-accent/10 text-accent border-accent/30' },
  failed: { label: 'Failed', cls: 'bg-destructive/10 text-destructive border-destructive/30' },
}

export function StatusBadge({ status }: { status: DocStatus }) {
  const s = STYLES[status] ?? STYLES.pending
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-xs ${s.cls} ${
        s.pulse ? 'animate-pulse' : ''
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.pulse ? 'bg-current' : 'bg-current/40'}`} aria-hidden />
      {s.label}
    </span>
  )
}
