import { NavLink, Outlet } from 'react-router-dom'
import {
  ClipboardText,
  FolderOpen,
  GearSix,
  ShieldCheck,
} from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { api } from '../api/client'

const NAV = [
  { to: '/', label: 'Knowledge Base', icon: FolderOpen, end: true },
  { to: '/new-review', label: 'New Review', icon: ClipboardText },
  { to: '/reviews', label: 'Review History', icon: ShieldCheck },
  { to: '/settings', label: 'Settings', icon: GearSix },
]

export function Layout() {
  const [ollama, setOllama] = useState<boolean | null>(null)

  useEffect(() => {
    const check = () =>
      api.health().then((h) => setOllama(h.ollama)).catch(() => setOllama(false))
    void check()
    const id = setInterval(check, 15000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="flex h-full min-h-screen bg-background text-foreground">
      <aside className="flex w-64 flex-col border-r border-border bg-muted/60 p-4">
        <div className="mb-8 flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-on-primary">
            <ShieldCheck size={22} weight="fill" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight">ASE Security</p>
            <p className="font-mono text-xs text-foreground/60">Review Agent</p>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-150 ${
                  isActive
                    ? 'bg-primary text-on-primary'
                    : 'text-foreground/75 hover:bg-border/60 hover:text-foreground'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon size={18} weight={isActive ? 'fill' : 'regular'} />
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-6 flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2.5">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              ollama === true
                ? 'bg-accent'
                : ollama === false
                  ? 'bg-destructive'
                  : 'bg-warning'
            }`}
            aria-hidden
          />
          <span className="text-xs text-foreground/70">
            Ollama {ollama === true ? 'connected' : ollama === false ? 'offline' : 'checking…'}
          </span>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto p-8">
        <Outlet />
      </main>
    </div>
  )
}
