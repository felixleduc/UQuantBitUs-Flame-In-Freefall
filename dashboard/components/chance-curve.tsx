"use client"

import * as React from "react"

import type { Test } from "@/lib/data"

// The model's chance a flame keeps burning along one variable (oxygen or air flow), with
// its likely band, and the matching flight tests as outcomes: kept burning along the top,
// went out along the bottom. Vertical markers name reference values (habitats, your value).

export type CurvePoint = { x: number; p: number; low: number; high: number }
export type Marker = { x: number; label: string; strong?: boolean }

const W = 720
const H = 300
const PAD = { left: 52, right: 16, top: 48, bottom: 56 }
const PLOT_W = W - PAD.left - PAD.right
const PLOT_H = H - PAD.top - PAD.bottom
const ROW = 16 // distance of the outcome rows from the plot, in px

const HALO = {
  paintOrder: "stroke",
  stroke: "var(--background)",
  strokeWidth: 4,
  strokeLinejoin: "round",
} as const

type Hover = { x: number; y: number; title: string; lines: string[] }

export function ChanceCurve({
  label,
  unit,
  domain,
  ticks,
  curve,
  tests,
  valueOf,
  markers,
  binWidth,
}: {
  label: string
  unit: string
  domain: [number, number]
  ticks: number[]
  curve: CurvePoint[]
  tests: Test[]
  valueOf: (t: Test) => number
  markers: Marker[]
  binWidth: number // tests within one bin share a dot
}) {
  const [hover, setHover] = React.useState<Hover | null>(null)
  const r1 = (n: number) => Math.round(n * 10) / 10
  const x = (v: number) =>
    r1(
      PAD.left +
        ((Math.min(Math.max(v, domain[0]), domain[1]) - domain[0]) /
          (domain[1] - domain[0])) *
          PLOT_W
    )
  const y = (p: number) => r1(PAD.top + (1 - p) * PLOT_H)
  const line = curve.map((c) => `${x(c.x)},${y(c.p)}`).join(" ")
  const band = [
    ...curve.map((c) => `${x(c.x)},${y(c.high)}`),
    ...[...curve].reverse().map((c) => `${x(c.x)},${y(c.low)}`),
  ].join(" ")
  const at = (v: number) =>
    curve.reduce(
      (best, c) => (Math.abs(c.x - v) < Math.abs(best.x - v) ? c : best),
      curve[0]
    )

  // Tests in the same bin are one dot at the bin centre, with their count inside
  const binned = (kept: boolean) => {
    const bins: Record<string, Test[]> = {}
    for (const t of tests.filter((t) => Boolean(t.sustained) === kept)) {
      const key = (
        (Math.floor(valueOf(t) / binWidth) + 0.5) *
        binWidth
      ).toFixed(2)
      ;(bins[key] ??= []).push(t)
    }
    return Object.entries(bins).map(([key, group]) => ({
      at: Number(key),
      group,
    }))
  }

  function show(e: React.MouseEvent, title: string, lines: string[]) {
    const box = (
      e.currentTarget as SVGElement
    ).ownerSVGElement!.getBoundingClientRect()
    setHover({ x: e.clientX - box.left, y: e.clientY - box.top, title, lines })
  }

  return (
    <div className="relative w-full" onMouseLeave={() => setHover(null)}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={`Chance a flame keeps burning by ${label}`}
      >
        {/* zones and grid */}
        <rect
          x={PAD.left}
          y={y(1)}
          width={PLOT_W}
          height={y(0.7) - y(1)}
          fill="var(--chart-2)"
          fillOpacity={0.08}
        />
        <rect
          x={PAD.left}
          y={y(0.3)}
          width={PLOT_W}
          height={y(0) - y(0.3)}
          fill="var(--chart-1)"
          fillOpacity={0.08}
        />
        {[0, 0.3, 0.5, 0.7, 1].map((p) => (
          <g key={p}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(p)}
              y2={y(p)}
              stroke="var(--border)"
            />
            <text
              x={PAD.left - 8}
              y={y(p) + 4}
              textAnchor="end"
              className="fill-muted-foreground text-[11px]"
            >
              {p * 100} %
            </text>
          </g>
        ))}
        <text
          x={W - PAD.right - 4}
          y={y(0.85) + 4}
          textAnchor="end"
          className="fill-muted-foreground text-[11px]"
        >
          Keeps burning
        </text>
        <text
          x={W - PAD.right - 4}
          y={y(0.15) + 4}
          textAnchor="end"
          className="fill-muted-foreground text-[11px]"
        >
          Goes out
        </text>

        {markers.map((m) => (
          <g key={m.label}>
            <line
              x1={x(m.x)}
              x2={x(m.x)}
              y1={18}
              y2={y(0)}
              stroke="var(--foreground)"
              strokeOpacity={m.strong ? 0.9 : 0.35}
              strokeWidth={m.strong ? 2 : 1}
              strokeDasharray={m.strong ? undefined : "3 3"}
            />
            <text
              x={x(m.x)}
              y={12}
              textAnchor="middle"
              className={
                m.strong
                  ? "fill-foreground text-[11px] font-medium"
                  : "fill-muted-foreground text-[11px]"
              }
              {...HALO}
            >
              {m.label}
            </text>
          </g>
        ))}

        {/* model: likely band and curve, in neutral ink so they read as a prediction, not as
            a burn zone; hovering anywhere on it reads the value */}
        <polygon points={band} fill="var(--foreground)" fillOpacity={0.12} />
        <polyline
          points={line}
          fill="none"
          stroke="var(--foreground)"
          strokeWidth={2.5}
        />
        <rect
          x={PAD.left}
          y={PAD.top}
          width={PLOT_W}
          height={PLOT_H}
          fill="transparent"
          onMouseMove={(e) => {
            const box = (
              e.currentTarget as SVGElement
            ).ownerSVGElement!.getBoundingClientRect()
            const v =
              domain[0] +
              ((((e.clientX - box.left) / box.width) * W - PAD.left) / PLOT_W) *
                (domain[1] - domain[0])
            const c = at(v)
            show(
              e,
              `Model: ${Math.round(c.p * 100)} % at ${Math.round(c.x * 10) / 10} ${unit}`,
              [
                `likely ${Math.round(c.low * 100)} to ${Math.round(c.high * 100)} %`,
              ]
            )
          }}
        />

        {/* flight tests: kept burning above the plot, went out below it */}
        <text
          x={PAD.left - 8}
          y={y(1) - ROW + 4}
          textAnchor="end"
          className="fill-muted-foreground text-[11px]"
        >
          Burned
        </text>
        <text
          x={PAD.left - 8}
          y={y(0) + ROW + 4}
          textAnchor="end"
          className="fill-muted-foreground text-[11px]"
        >
          Out
        </text>
        {[true, false].map((kept) =>
          binned(kept).map(({ at: v, group }) => {
            const cy = kept ? y(1) - ROW : y(0) + ROW
            const r = group.length > 1 ? 8 : 4
            return (
              <g
                key={`${kept}-${v}`}
                onMouseEnter={(e) =>
                  show(
                    e,
                    `${group.length} test${group.length > 1 ? "s" : ""} ${kept ? "kept burning" : "went out"}, ${Math.round((v - binWidth / 2) * 10) / 10} to ${Math.round((v + binWidth / 2) * 10) / 10} ${unit}`,
                    group
                      .slice(0, 5)
                      .map(
                        (t) =>
                          `${t.investigation} ${t.test_id}: ${t.outcome ?? ""}`
                      )
                      .concat(
                        group.length > 5 ? [`and ${group.length - 5} more`] : []
                      )
                  )
                }
              >
                <circle
                  cx={x(v)}
                  cy={cy}
                  r={r}
                  fill={kept ? "var(--chart-2)" : "var(--chart-1)"}
                  stroke="var(--background)"
                  strokeWidth={1}
                />
                {group.length > 1 && (
                  <text
                    x={x(v)}
                    y={cy + 3.5}
                    textAnchor="middle"
                    className="pointer-events-none fill-white text-[10px] font-medium"
                  >
                    {group.length}
                  </text>
                )}
              </g>
            )
          })
        )}

        {ticks.map((v) => (
          <text
            key={v}
            x={x(v)}
            y={H - PAD.bottom + ROW + 14}
            textAnchor="middle"
            className="fill-muted-foreground text-[11px]"
          >
            {v}
          </text>
        ))}
        <text
          x={PAD.left + PLOT_W / 2}
          y={H - 4}
          textAnchor="middle"
          className="fill-muted-foreground text-[11px]"
        >
          {label}, {unit}
        </text>
      </svg>

      {hover && (
        <div
          className="pointer-events-none absolute z-10 w-64 rounded-md border bg-popover p-2.5 text-popover-foreground shadow-md"
          style={{
            left: hover.x + 14,
            top: hover.y + 14,
            transform:
              hover.x > 400 ? "translateX(calc(-100% - 28px))" : undefined,
          }}
        >
          <p className="text-sm font-medium">{hover.title}</p>
          {hover.lines.filter(Boolean).map((l) => (
            <p key={l} className="text-xs text-muted-foreground">
              {l}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
