export interface Step {
  key: string
  label: string
}

const DEFAULT_STEPS: Step[] = [
  { key: 'facts', label: 'Extract facts' },
  { key: 'retrieve', label: 'Retrieve context' },
  { key: 'rules', label: 'Apply rules' },
  { key: 'decide', label: 'Decide' },
]

interface Props {
  current: number
  running: boolean
  steps?: Step[]
}

export function Stepper({ current, running, steps = DEFAULT_STEPS }: Props) {
  return (
    <ol className="flex flex-wrap items-center justify-center gap-2" aria-label="Review progress">
      {steps.map((step, i) => {
        const done = i < current
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
            {i < steps.length - 1 && (
              <span className={`h-px w-6 ${done || active ? 'bg-accent' : 'bg-border'}`} aria-hidden />
            )}
          </li>
        )
      })}
    </ol>
  )
}
