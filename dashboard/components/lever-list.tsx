import type { Lever } from "@/lib/model"
import { pct } from "@/lib/scenario"
import { cn } from "@/lib/utils"

const signed = (points: number) =>
  `${points > 0 ? "+" : points < 0 ? "−" : ""}${Math.abs(points)}`

// One change at a time from the current scenario, ranked by effect. Each row: the action,
// the chance a flame keeps spreading before and after it, and the difference in percentage
// points as a bar from a centre line (left, blue: safer; right, orange: riskier).
export function LeverList({ base, levers }: { base: number; levers: Lever[] }) {
  const rows = levers.map((l) => ({ ...l, points: pct(l.delta) }))
  const scale = Math.max(...rows.map((l) => Math.abs(l.points)), 1)
  const grid = "grid grid-cols-[1fr_72px_56px_84px] items-center gap-3"

  return (
    <ul className="flex flex-col gap-3">
      <li aria-hidden className={cn(grid, "text-xs text-muted-foreground")}>
        <span>If you…</span>
        <span className="col-span-2 text-right">Change, % points</span>
        <span className="text-right">Chance becomes</span>
      </li>
      {rows.map((l) => (
        <li key={l.id} className={cn(grid, "text-sm")}>
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-medium">{l.label}</span>
            <span className="truncate text-xs text-muted-foreground">
              {l.change}
            </span>
          </span>
          <span
            className="relative h-3"
            role="img"
            aria-label={`${signed(l.points)} percentage points`}
          >
            <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
            <span
              className={cn(
                "absolute inset-y-0.5 rounded-sm",
                l.points <= 0 ? "right-1/2 bg-chart-1" : "left-1/2 bg-chart-2"
              )}
              style={{ width: `${(Math.abs(l.points) / scale) * 50}%` }}
            />
          </span>
          <span className="text-right text-muted-foreground tabular-nums">
            {signed(l.points)} pts
          </span>
          <span className="text-right tabular-nums">
            <span className="text-muted-foreground">{pct(base)} → </span>
            <span className="font-medium">{pct(l.probability)} %</span>
          </span>
        </li>
      ))}
    </ul>
  )
}
