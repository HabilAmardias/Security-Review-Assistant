const STEPS = [
  { key: 'facts', label: 'Extract facts' },
  { key: 'retrieve', label: 'Retrieve context' },
  { key: 'rules', label: 'Apply rules' },
  { key: 'decide', label: 'Decide' },
]

interface Props {
  current: number
  running: boolean
}

export function Stepper({ current, running }: Props) {
  return (
    <ol className="flex items-center gap-2" aria-label="Review pipeline progress">
      {STEPS.map((step, i) => {
        const done = i < current || (!running && i <= current && current >= STEPS.length)
        const active = running && i === current
        return (
          <li key={step.key} className="flex items-center gap-2">
            <div className="flex items-center gap-2">
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                  done
                    ? 'bg-accent text-white'
                    : active
                      ? 'bg-primary text-white'
                      : 'bg-muted text-foreground/50'
                }`}
              >
                {done ? '✓' : i + 1}
              </span>
              <span
                className={`text-sm ${
                  active ? 'font-semibold text-foreground' : done ? 'text-foreground/80' : 'text-foreground/50'
                }`}
              >
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <span className={`h-px w-6 ${done ? 'bg-accent' : 'bg-border'}`} aria-hidden />
            )}
          </li>
        )
      })}
    </ol>
  )
}
