import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Trash } from '@phosphor-icons/react'
import { api } from '../api/client'
import { useReviews } from '../hooks/useReviews'
import type { TestLevel } from '../types'

const LEVEL_COLOR: Record<TestLevel, string> = {
  pentest: 'text-destructive',
  dast: 'text-warning',
  none: 'text-accent',
}

export function ReviewHistory() {
  const { reviews, error, loading } = useReviews()
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [deleteMsg, setDeleteMsg] = useState<string | null>(null)

  const remove = async (id: string) => {
    setDeleteMsg(null)
    try {
      await api.deleteReview(id)
      setConfirmId(null)
    } catch (err) {
      setDeleteMsg(err instanceof Error ? err.message : String(err))
      setConfirmId(null)
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">Review History</h1>
        <p className="mt-1 text-sm text-foreground/60">
          Every review is audited with inputs, rules fired, sources retrieved, and decisions.
        </p>
      </header>

      {deleteMsg && <p className="mb-4 text-sm text-destructive">{deleteMsg}</p>}
      {loading && !reviews.length && <p className="text-sm text-foreground/50">Loading…</p>}
      {error && <p className="text-sm text-destructive">Failed to load: {error}</p>}

      {!loading && reviews.length === 0 && (
        <p className="rounded-xl border border-dashed border-border px-6 py-10 text-center text-sm text-foreground/50">
          No reviews yet. Start one from the New Review page.
        </p>
      )}

      <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-background">
        {reviews.map((r) => {
          const level = r.final_decision?.test_level
          return (
            <li key={r.id} className="group relative">
              <Link
                to={`/reviews/${r.id}`}
                className="flex items-center gap-4 px-5 py-4 pr-16 transition-colors hover:bg-muted/60"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {r.frd_name} <span className="text-foreground/40">+</span> {r.nfrd_name}
                  </p>
                  <p className="mt-0.5 font-mono text-xs text-foreground/50">
                    {new Date(r.created_at).toLocaleString()} · {r.retrieved_sources.length} sources
                    {r.rules_fired.length > 0 && ` · ${r.rules_fired.length} rules`}
                  </p>
                </div>
                {r.status === 'running' && (
                  <span className="rounded-full border border-secondary/40 bg-secondary/10 px-3 py-1 font-mono text-xs text-secondary animate-pulse">
                    running…
                  </span>
                )}
                {r.status === 'failed' && (
                  <span className="rounded-full border border-destructive/40 bg-destructive/10 px-3 py-1 font-mono text-xs text-destructive">
                    failed
                  </span>
                )}
                {r.status === 'completed' && level && (
                  <span
                    className={`rounded-full border border-border bg-muted px-3 py-1 font-mono text-xs font-bold uppercase ${LEVEL_COLOR[level]}`}
                  >
                    {level}
                  </span>
                )}
                <ArrowRight size={18} className="text-foreground/40" />
              </Link>
              <div className="absolute right-3 top-1/2 -translate-y-1/2 opacity-0 transition-opacity group-hover:opacity-100">
                {confirmId === r.id ? (
                  <span className="flex items-center gap-1 rounded-lg border border-border bg-background px-2 py-1 shadow-sm">
                    <span className="text-xs text-foreground/70">Delete?</span>
                    <button
                      onClick={() => void remove(r.id)}
                      className="rounded bg-destructive px-2 py-1 text-xs font-semibold text-white hover:opacity-90"
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setConfirmId(null)}
                      className="rounded px-2 py-1 text-xs hover:bg-muted"
                    >
                      No
                    </button>
                  </span>
                ) : (
                  <button
                    onClick={() => setConfirmId(r.id)}
                    className="rounded-lg border border-border p-2 text-foreground/60 hover:bg-destructive/10 hover:text-destructive"
                    title="Delete review"
                    aria-label={`Delete review ${r.frd_name} + ${r.nfrd_name}`}
                  >
                    <Trash size={16} />
                  </button>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
