import type { Lever } from "@/lib/demo-model"
import { pct } from "@/lib/scenario"
import { cn } from "@/lib/utils"

const signed = (points: number) => `${points > 0 ? "+" : ""}${points}`

// Changes ranked by effect, as diverging bars from a centre line:
// left (blue) lowers the chance a flame keeps spreading, right (orange) raises it.
export function LeverList({ levers }: { levers: Lever[] }) {
  const rows = levers.map((l) => ({ ...l, points: pct(l.delta) }))
  const scale = Math.max(...rows.map((l) => Math.abs(l.points)), 1)

  return (
    <ul className="flex flex-col gap-3">
      <li
        aria-hidden
        className="grid grid-cols-[1fr_80px_40px_48px] gap-3 text-xs text-muted-foreground"
      >
        <span>Change</span>
        <span className="col-span-2 text-right">Effect, points</span>
        <span className="text-right">Result</span>
      </li>
      {rows.map((l) => (
        <li
          key={l.id}
          className="grid grid-cols-[1fr_80px_40px_48px] items-center gap-3 text-sm"
        >
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-medium">{l.label}</span>
            <span className="truncate text-xs text-muted-foreground">
              {l.change}
            </span>
          </span>
          <span
            className="relative h-3"
            role="img"
            aria-label={`${signed(l.points)} points`}
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
            {signed(l.points)}
          </span>
          <span className="text-right font-medium tabular-nums">
            {pct(l.probability)} %
          </span>
        </li>
      ))}
    </ul>
  )
}
