"use client"

import * as React from "react"
import { FlaskConicalIcon } from "lucide-react"

import { NothingFound } from "@/components/nothing-found"
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
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { tests as allTests, type Test } from "@/lib/data"
import { flownTests } from "@/lib/evidence"
import { MATERIALS } from "@/lib/scenario"
import { cn } from "@/lib/utils"

// Air-flow ranges, cm/s: narrow where most tests were flown (around 5 and 10 cm/s)
const FLOWS = [
  { from: 0, to: 2, label: "0 to 2" },
  { from: 2, to: 5, label: "2 to 5" },
  { from: 5, to: 8, label: "5 to 8" },
  { from: 8, to: 12, label: "8 to 12" },
  { from: 12, to: 20, label: "12 to 20" },
  { from: 20, to: Infinity, label: "20 +" },
]
const flowIndex = (flow: number) =>
  FLOWS.findIndex((f) => flow >= f.from && flow < f.to)

const one = (n: number) => Math.round(n * 10) / 10

// Every solid was flown near sea-level pressure: stated once, it is not a variable here
const pressures = allTests.flatMap((t) =>
  t.pressure_atm === undefined ? [] : [t.pressure_atm]
)
const PRESSURE = `${Math.min(...pressures)} to ${Math.round(Math.max(...pressures) * 100) / 100} atm`

// Blue when every test went out, orange when every test kept burning, grey when split.
// The count is always printed: colour only helps.
function cellColor(burned: number, total: number) {
  const share = burned / total
  const strength = Math.round(Math.abs(share - 0.5) * 2 * 70)
  const hue = share > 0.5 ? "var(--chart-2)" : "var(--chart-1)"
  return `color-mix(in oklch, ${hue} ${strength}%, var(--muted))`
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
  const ofMaterial = flownTests(scenario.material).filter(
    (t) => t.flow_cm_s !== undefined
  )
  const shapes = [...new Set(ofMaterial.map((t) => t.geometry ?? "unknown"))]
  // The shape filter resets when the material changes
  const [choice, setChoice] = React.useState({ material: "", shape: "all" })
  const shape = choice.material === scenario.material ? choice.shape : "all"
  const flown = ofMaterial.filter(
    (t) => shape === "all" || (t.geometry ?? "unknown") === shape
  )

  const burned = flown.filter((t) => t.sustained)
  const out = flown.filter((t) => !t.sustained)
  const lowestBurning = burned.reduce<Test | undefined>(
    (low, t) => (!low || t.o2_percent! < low.o2_percent! ? t : low),
    undefined
  )
  const highestOut = out.reduce<Test | undefined>(
    (high, t) => (!high || t.o2_percent! > high.o2_percent! ? t : high),
    undefined
  )

  // One row per point of oxygen, highest first
  const o2s = flown.map((t) => Math.floor(t.o2_percent!))
  const rows = o2s.length
    ? Array.from(
        { length: Math.max(...o2s) - Math.min(...o2s) + 1 },
        (_, i) => Math.max(...o2s) - i
      )
    : []
  const cell = (o2: number, f: number) =>
    flown.filter(
      (t) => Math.floor(t.o2_percent!) === o2 && flowIndex(t.flow_cm_s!) === f
    )
  const yourRow = Math.floor(scenario.o2Percent)
  const yourFlow = flowIndex(scenario.flowCmS)

  return (
    <>
      <PageHeader title="Flammability map" />
      <ScenarioBar />
      <div className="flex flex-col gap-4 p-4 md:p-8">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle>
              {material}: flight tests by oxygen and air flow
            </CardTitle>
            {shapes.length > 1 && (
              <CardAction>
                <ToggleGroup
                  type="single"
                  variant="outline"
                  size="sm"
                  value={shape}
                  onValueChange={(v) =>
                    v && setChoice({ material: scenario.material, shape: v })
                  }
                  className="flex-wrap"
                  aria-label="Sample shape"
                >
                  <ToggleGroupItem value="all">All shapes</ToggleGroupItem>
                  {shapes.map((s) => (
                    <ToggleGroupItem key={s} value={s}>
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
              </CardAction>
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-6 overflow-x-auto">
            {rows.length === 0 ? (
              <NothingFound
                icon={FlaskConicalIcon}
                title={`No flight test of ${material}`}
                reason="No test of this material has both an oxygen level and an air flow recorded."
              />
            ) : (
              <>
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

                <table className="w-full min-w-[560px] border-separate border-spacing-1 text-sm">
                  <thead>
                    <tr className="text-xs text-muted-foreground">
                      <th className="w-20 text-left font-normal">O2 \ flow</th>
                      {FLOWS.map((f) => (
                        <th key={f.label} className="font-normal">
                          {f.label} cm/s
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((o2) => (
                      <tr key={o2}>
                        <th className="text-left font-normal text-muted-foreground tabular-nums">
                          {o2} %
                        </th>
                        {FLOWS.map((f, i) => {
                          const tests = cell(o2, i)
                          const kept = tests.filter((t) => t.sustained).length
                          const yours = o2 === yourRow && i === yourFlow
                          const ring = yours && "ring-2 ring-foreground"
                          if (tests.length === 0)
                            return (
                              <td
                                key={f.label}
                                className={cn(
                                  "h-10 rounded-md text-center text-muted-foreground",
                                  ring
                                )}
                              >
                                ·
                              </td>
                            )
                          return (
                            <td key={f.label} className="h-10 p-0">
                              <HoverCard openDelay={80} closeDelay={80}>
                                <HoverCardTrigger asChild>
                                  <button
                                    type="button"
                                    className={cn(
                                      "size-full rounded-md font-medium tabular-nums",
                                      ring
                                    )}
                                    style={{
                                      backgroundColor: cellColor(
                                        kept,
                                        tests.length
                                      ),
                                    }}
                                    aria-label={`${o2} % O2, ${f.label} cm/s: ${kept} of ${tests.length} kept burning`}
                                  >
                                    {kept} / {tests.length}
                                  </button>
                                </HoverCardTrigger>
                                <HoverCardContent className="w-72">
                                  <p className="text-sm font-medium">
                                    {kept} of {tests.length} kept burning
                                  </p>
                                  <p className="mb-2 text-xs text-muted-foreground">
                                    {o2} % O2, {f.label} cm/s
                                  </p>
                                  <ul className="flex flex-col gap-1 text-xs">
                                    {tests.slice(0, 6).map((t) => (
                                      <li
                                        key={`${t.psi_id}-${t.test_id}`}
                                        className="flex justify-between gap-3"
                                      >
                                        <span>
                                          {t.investigation} {t.test_id}
                                        </span>
                                        <span className="text-muted-foreground">
                                          {t.sustained
                                            ? "kept burning"
                                            : "went out"}
                                        </span>
                                      </li>
                                    ))}
                                    {tests.length > 6 && (
                                      <li className="text-muted-foreground">
                                        and {tests.length - 6} more
                                      </li>
                                    )}
                                  </ul>
                                </HoverCardContent>
                              </HoverCard>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <span
                      className="size-3 rounded-sm"
                      style={{ backgroundColor: cellColor(0, 1) }}
                    />
                    All went out
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span
                      className="size-3 rounded-sm"
                      style={{ backgroundColor: cellColor(1, 1) }}
                    />
                    All kept burning
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="size-3 rounded-sm ring-2 ring-foreground" />
                    Your scenario ({scenario.o2Percent} % O2, {scenario.flowCmS}{" "}
                    cm/s)
                  </span>
                  <span className="ml-auto">All tests flown at {PRESSURE}</span>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
