"use client"

import * as React from "react"

import type { Test } from "@/lib/data"
import { burnProbability, model } from "@/lib/model"
import type { Scenario } from "@/lib/scenario"

const FLOW_MAX = 50 // cm/s
const O2_MIN = 12 // %
const W = 720
const H = 400
const PAD = { left: 48, right: 12, top: 12, bottom: 40 }
const PLOT_W = W - PAD.left - PAD.right
const PLOT_H = H - PAD.top - PAD.bottom

// Blue (goes out) through grey (50 %) to orange (keeps burning), as on the rest of the site
export function heatColor(p: number) {
  const strength = Math.round(Math.abs(p - 0.5) * 2 * 75)
  const hue = p > 0.5 ? "var(--chart-2)" : "var(--chart-1)"
  return `color-mix(in oklch, ${hue} ${strength}%, var(--muted))`
}

type Hover = { x: number; y: number; title: string; lines: string[] }

export function FlammabilityHeatmap({
  scenario,
  shape,
  tests,
}: {
  scenario: Scenario
  shape?: string
  tests: Test[]
}) {
  const o2Max = Math.max(36, Math.ceil(scenario.o2Percent + 2))
  const x = (flow: number) => PAD.left + (flow / FLOW_MAX) * PLOT_W
  const y = (o2: number) =>
    PAD.top + (1 - (o2 - O2_MIN) / (o2Max - O2_MIN)) * PLOT_H
  const at = (o2: number, flow: number) =>
    burnProbability({ ...scenario, o2Percent: o2, flowCmS: flow }, shape)

  // Model surface: 1 cm/s by 0.5 % cells, recomputed only when its inputs change
  const { cells, boundary } = React.useMemo(() => {
    const cells: { flow: number; o2: number; p: number }[] = []
    for (let o2 = O2_MIN; o2 < o2Max; o2 += 0.5)
      for (let flow = 0; flow < FLOW_MAX; flow += 1)
        cells.push({ flow, o2, p: at(o2 + 0.25, flow + 0.5) })
    // 50 % line: the oxygen where the chance crosses one half, for each flow
    const boundary: string[] = []
    for (let flow = 0; flow <= FLOW_MAX; flow += 1) {
      let low = O2_MIN
      let high = o2Max
      if (at(low, flow) >= 0.5 || at(high, flow) < 0.5) continue
      for (let k = 0; k < 25; k++) {
        const mid = (low + high) / 2
        if (at(mid, flow) < 0.5) low = mid
        else high = mid
      }
      boundary.push(`${x(flow)},${y(high)}`)
    }
    return { cells, boundary }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario.material, scenario.pressureAtm, shape, o2Max])

  const [hover, setHover] = React.useState<Hover | null>(null)
  const [flownLow, flownHigh] = model.solids.o2_range
  const cellW = PLOT_W / FLOW_MAX
  const cellH = (0.5 / (o2Max - O2_MIN)) * PLOT_H

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    if ((e.target as Element).getAttribute("data-point")) return
    const box = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - box.left) / box.width) * W
    const py = ((e.clientY - box.top) / box.height) * H
    const flow = ((px - PAD.left) / PLOT_W) * FLOW_MAX
    const o2 = O2_MIN + (1 - (py - PAD.top) / PLOT_H) * (o2Max - O2_MIN)
    if (flow < 0 || flow > FLOW_MAX || o2 < O2_MIN || o2 > o2Max)
      return setHover(null)
    setHover({
      x: e.clientX - box.left,
      y: e.clientY - box.top,
      title: `${Math.round(at(o2, flow) * 100)} % chance to keep burning`,
      lines: [
        `${o2.toFixed(1)} % O2, ${flow.toFixed(0)} cm/s, ${scenario.pressureAtm} atm (model)`,
      ],
    })
  }

  return (
    <div className="relative w-full" onMouseLeave={() => setHover(null)}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label="Model chance a flame keeps burning by oxygen and air flow, with the flight tests"
        onMouseMove={onMove}
      >
        {cells.map((c) => (
          <rect
            key={`${c.o2}-${c.flow}`}
            x={x(c.flow)}
            y={y(c.o2 + 0.5)}
            width={cellW + 0.5}
            height={cellH + 0.5}
            fill={heatColor(c.p)}
          />
        ))}

        {/* Oxygen range where solids were actually flown */}
        <rect
          x={x(0)}
          y={y(flownHigh)}
          width={PLOT_W}
          height={y(flownLow) - y(flownHigh)}
          fill="none"
          stroke="var(--foreground)"
          strokeOpacity={0.5}
          strokeDasharray="2 4"
        />
        <polyline
          points={boundary.join(" ")}
          fill="none"
          stroke="var(--foreground)"
          strokeWidth={2}
          strokeDasharray="6 4"
        />

        {tests.map((t) => (
          <circle
            key={`${t.psi_id}-${t.test_id}`}
            data-point="1"
            cx={x(Math.min(t.flow_cm_s!, FLOW_MAX))}
            cy={y(t.o2_percent!)}
            r={4}
            className="cursor-default"
            fill={t.sustained ? "var(--foreground)" : "var(--background)"}
            stroke={t.sustained ? "var(--background)" : "var(--foreground)"}
            strokeWidth={1.5}
            onMouseEnter={(e) => {
              const box = (
                e.currentTarget.ownerSVGElement as SVGSVGElement
              ).getBoundingClientRect()
              setHover({
                x: e.clientX - box.left,
                y: e.clientY - box.top,
                title: `${t.investigation} ${t.test_id}: ${t.sustained ? "kept burning" : "went out"}`,
                lines: [
                  `${Math.round(t.o2_percent! * 10) / 10} % O2, ${t.flow_cm_s} cm/s, ${t.geometry ?? "sample"}`,
                  t.outcome ?? "",
                ],
              })
            }}
          />
        ))}

        <circle
          cx={x(Math.min(scenario.flowCmS, FLOW_MAX))}
          cy={y(scenario.o2Percent)}
          r={9}
          fill="none"
          stroke="var(--foreground)"
          strokeWidth={2.5}
        />

        {/* Axes */}
        {[0, 10, 20, 30, 40, 50].map((f) => (
          <text
            key={f}
            x={x(f)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            className="fill-muted-foreground text-[11px]"
          >
            {f}
          </text>
        ))}
        <text
          x={PAD.left + PLOT_W / 2}
          y={H - 4}
          textAnchor="middle"
          className="fill-muted-foreground text-[11px]"
        >
          Air flow past the sample, cm/s
        </text>
        {Array.from(
          { length: Math.floor((o2Max - O2_MIN) / 4) + 1 },
          (_, i) => O2_MIN + 4 * i
        ).map((o) => (
          <text
            key={o}
            x={PAD.left - 6}
            y={y(o) + 4}
            textAnchor="end"
            className="fill-muted-foreground text-[11px]"
          >
            {o} %
          </text>
        ))}
        <text
          transform={`translate(12 ${PAD.top + PLOT_H / 2}) rotate(-90)`}
          textAnchor="middle"
          className="fill-muted-foreground text-[11px]"
        >
          Oxygen
        </text>
      </svg>

      {hover && (
        <div
          className="pointer-events-none absolute z-10 w-64 rounded-md border bg-popover p-2.5 text-popover-foreground shadow-md"
          style={{
            left: Math.min(hover.x + 14, 9999),
            top: hover.y + 14,
            transform:
              hover.x > 420 ? "translateX(calc(-100% - 28px))" : undefined,
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
