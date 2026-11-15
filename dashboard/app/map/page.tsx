"use client"

import { useEffect, useRef, useState } from "react"

import { PageHeader } from "@/components/page-header"
import { ScenarioBar } from "@/components/scenario-bar"
import { useScenario } from "@/components/scenario-provider"
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { tests as allTests, type Test } from "@/lib/data"
import { flownTests } from "@/lib/evidence"
import { model } from "@/lib/model"
import { MATERIALS } from "@/lib/scenario"

const one = (n: number) => Math.round(n * 10) / 10
const MAP_SCALE = 32
const MAP_WIDTH = (model.flow.length - 1) * MAP_SCALE + 1
const MAP_HEIGHT = (model.o2.length - 1) * MAP_SCALE + 1

// Every solid was flown near sea-level pressure: stated once, it is not a variable here
const pressures = allTests.flatMap((t) =>
  t.pressure_atm === undefined ? [] : [t.pressure_atm]
)
const PRESSURE = `${Math.min(...pressures)} to ${Math.round(Math.max(...pressures) * 100) / 100} atm`

type Grid = number[][]
type HeatPoint = {
  o2: number
  flow: number
  probability: number
  low: number
  high: number
}

function sampleGrid(grid: Grid, row: number, column: number) {
  const y = Math.min(Math.max(row, 0), grid.length - 1)
  const x = Math.min(Math.max(column, 0), grid[0].length - 1)
  const y0 = Math.floor(y)
  const x0 = Math.floor(x)
  const y1 = Math.min(y0 + 1, grid.length - 1)
  const x1 = Math.min(x0 + 1, grid[0].length - 1)
  const fy = y - y0
  const fx = x - x0
  const top = grid[y0][x0] * (1 - fx) + grid[y0][x1] * fx
  const bottom = grid[y1][x0] * (1 - fx) + grid[y1][x1] * fx
  return top * (1 - fy) + bottom * fy
}

function gridPosition(axis: number[], value: number) {
  const clamped = Math.min(Math.max(value, axis[0]), axis[axis.length - 1])
  const lower = Math.min(
    Math.max(
      axis.findLastIndex((point) => point <= clamped),
      0
    ),
    axis.length - 2
  )
  return lower + (clamped - axis[lower]) / (axis[lower + 1] - axis[lower])
}

function axisValue(axis: number[], position: number) {
  const lower = Math.floor(position)
  const upper = Math.min(lower + 1, axis.length - 1)
  const fraction = position - lower
  return axis[lower] * (1 - fraction) + axis[upper] * fraction
}

function HeatMap({
  materialModel,
  o2Percent,
  flowCmS,
}: {
  materialModel: (typeof model.materials)[string]
  o2Percent: number
  flowCmS: number
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hovered, setHovered] = useState<HeatPoint>()
  const o2Position = gridPosition(model.o2, o2Percent)
  const flowPosition = gridPosition(model.flow, flowCmS)

  useEffect(() => {
    const canvas = canvasRef.current
    const context = canvas?.getContext("2d")
    if (!canvas || !context) return

    const draw = () => {
      const style = getComputedStyle(canvas)
      context.fillStyle = style.getPropertyValue("--chart-1").trim()
      context.fillRect(0, 0, 1, 1)
      context.fillStyle = style.getPropertyValue("--chart-2").trim()
      context.fillRect(1, 0, 1, 1)
      const palette = context.getImageData(0, 0, 2, 1).data

      const image = context.createImageData(MAP_WIDTH, MAP_HEIGHT)
      for (let y = 0; y < MAP_HEIGHT; y += 1) {
        const row =
          ((MAP_HEIGHT - 1 - y) / (MAP_HEIGHT - 1)) * (model.o2.length - 1)
        for (let x = 0; x < MAP_WIDTH; x += 1) {
          const column = (x / (MAP_WIDTH - 1)) * (model.flow.length - 1)
          const probability = sampleGrid(materialModel.p, row, column)
          const offset = (y * MAP_WIDTH + x) * 4
          for (let channel = 0; channel < 3; channel += 1) {
            image.data[offset + channel] = Math.round(
              palette[channel] * (1 - probability) +
                palette[channel + 4] * probability
            )
          }
          image.data[offset + 3] = 255
        }
      }
      context.putImageData(image, 0, 0)
    }

    draw()
    const themeObserver = new MutationObserver(draw)
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    })
    return () => themeObserver.disconnect()
  }, [materialModel])

  function showPoint(clientX: number, clientY: number, rect: DOMRect) {
    const column =
      ((clientX - rect.left) / rect.width) * (model.flow.length - 1)
    const row =
      model.o2.length -
      1 -
      ((clientY - rect.top) / rect.height) * (model.o2.length - 1)
    setHovered({
      o2: axisValue(model.o2, row),
      flow: axisValue(model.flow, column),
      probability: sampleGrid(materialModel.p, row, column),
      low: sampleGrid(materialModel.low, row, column),
      high: sampleGrid(materialModel.high, row, column),
    })
  }

  return (
    <>
      <div className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-x-2 gap-y-2">
        <span className="text-right text-xs text-muted-foreground">O2 %</span>
        <div className="relative h-4 text-xs text-muted-foreground tabular-nums">
          {model.flow.map((flow, index) => (
            <span
              key={flow}
              className="absolute top-0"
              style={{
                left: `${(index / (model.flow.length - 1)) * 100}%`,
                transform:
                  index === 0
                    ? "none"
                    : index === model.flow.length - 1
                      ? "translateX(-100%)"
                      : "translateX(-50%)",
              }}
            >
              {flow}
            </span>
          ))}
        </div>
        <div
          aria-hidden="true"
          className="flex flex-col justify-between text-right text-xs text-muted-foreground tabular-nums"
        >
          {[...model.o2].reverse().map((o2) => (
            <span key={o2}>{o2}</span>
          ))}
        </div>
        <div className="relative">
          <canvas
            ref={canvasRef}
            aria-label="Continuous heat map of predicted sustained-burning probability by oxygen and air flow"
            className="block h-auto w-full rounded-md"
            height={MAP_HEIGHT}
            onPointerLeave={() => setHovered(undefined)}
            onPointerMove={(event) =>
              showPoint(
                event.clientX,
                event.clientY,
                event.currentTarget.getBoundingClientRect()
              )
            }
            role="img"
            width={MAP_WIDTH}
          />
          <span
            aria-hidden="true"
            className="pointer-events-none absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-foreground shadow"
            style={{
              left: `${(flowPosition / (model.flow.length - 1)) * 100}%`,
              top: `${(1 - o2Position / (model.o2.length - 1)) * 100}%`,
            }}
          />
        </div>
      </div>

      <p aria-live="polite" className="min-h-5 text-xs text-muted-foreground">
        {hovered
          ? `${one(hovered.o2)}% O2 · ${one(hovered.flow)} cm/s: ${Math.round(hovered.probability * 100)}% predicted chance of sustained burning (likely range ${Math.round(hovered.low * 100)}–${Math.round(hovered.high * 100)}%)`
          : "Hover over the heat map to inspect a prediction and its likely range."}
      </p>

      <table className="sr-only">
        <caption>
          Predicted probability of sustained burning and likely range by oxygen
          and air flow
        </caption>
        <thead>
          <tr>
            <th scope="col">O2 %</th>
            {model.flow.map((flow) => (
              <th key={flow} scope="col">
                {flow} cm/s
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[...model.o2].reverse().map((o2, displayRow) => {
            const row = model.o2.length - 1 - displayRow
            return (
              <tr key={o2}>
                <th scope="row">{o2}</th>
                {model.flow.map((flow, column) => (
                  <td key={flow}>
                    {Math.round(materialModel.p[row][column] * 100)}% predicted;
                    likely range{" "}
                    {Math.round(materialModel.low[row][column] * 100)}–
                    {Math.round(materialModel.high[row][column] * 100)}%
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </>
  )
}

function Limit({ label, test }: { label: string; test: Test }) {
  return (
    <div>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-semibold tabular-nums">
        {one(test.o2_percent!)} % O2
      </p>
      <p className="text-xs text-muted-foreground">
        {test.investigation} {test.test_id} at {test.flow_cm_s} cm/s
      </p>
    </div>
  )
}

export default function MapPage() {
  const { scenario } = useScenario()
  const material = MATERIALS[scenario.material].label
  const materialModel =
    model.materials[scenario.material] ?? model.materials.PMMA
  const flightTests = flownTests(scenario.material).filter(
    (t) => t.flow_cm_s !== undefined
  )

  const burned = flightTests.filter((t) => t.sustained)
  const out = flightTests.filter((t) => !t.sustained)
  const lowestBurning = burned.reduce<Test | undefined>(
    (low, t) => (!low || t.o2_percent! < low.o2_percent! ? t : low),
    undefined
  )
  const highestOut = out.reduce<Test | undefined>(
    (high, t) => (!high || t.o2_percent! > high.o2_percent! ? t : high),
    undefined
  )
  return (
    <>
      <PageHeader title="Flammability heat map" />
      <ScenarioBar />
      <div className="flex flex-col gap-4 p-4 md:p-8">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>
              {material}: predicted chance of sustained burning on{" "}
              {materialModel.geometry}
            </CardTitle>
            <CardAction className="text-xs text-muted-foreground">
              Model trained on {materialModel.tests} flight tests
            </CardAction>
          </CardHeader>
          <CardContent className="flex flex-col gap-6 overflow-x-auto">
            {flightTests.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No flight tests are available for comparison; the heat map shows
                model estimates.
              </p>
            ) : null}

            {(lowestBurning || highestOut) && (
              <div className="grid gap-4 sm:grid-cols-2">
                {lowestBurning && (
                  <Limit
                    label="Lowest oxygen where a flame kept burning"
                    test={lowestBurning}
                  />
                )}
                {highestOut && (
                  <Limit
                    label="Highest oxygen where a flame went out"
                    test={highestOut}
                  />
                )}
              </div>
            )}

            <div className="min-w-[920px]">
              <p className="mb-2 text-right text-xs text-muted-foreground">
                Air flow (cm/s)
              </p>
              <HeatMap
                materialModel={materialModel}
                o2Percent={scenario.o2Percent}
                flowCmS={scenario.flowCmS}
              />
            </div>

            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-2">
                Lower chance
                <span
                  className="h-2 w-32 rounded-full"
                  style={{
                    background:
                      "linear-gradient(to right, var(--chart-1), var(--chart-2))",
                  }}
                />
                Higher chance
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-3 rounded-full border-2 border-background bg-foreground shadow" />
                Your scenario ({scenario.o2Percent} % O2, {scenario.flowCmS}{" "}
                cm/s)
              </span>
              <span className="ml-auto">
                Flight tests flown at {PRESSURE}; model does not vary pressure
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
