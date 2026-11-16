"use client"

import * as React from "react"
import { FlaskConicalIcon } from "lucide-react"

import { ChanceCurve, type Marker } from "@/components/chance-curve"
import { NothingFound } from "@/components/nothing-found"
import { PageHeader } from "@/components/page-header"
import { ScenarioBar } from "@/components/scenario-bar"
import { useScenario } from "@/components/scenario-provider"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { Test } from "@/lib/data"
import { flownTests } from "@/lib/evidence"
import { burnProbability, likelyRange, model } from "@/lib/model"
import { HABITATS, MATERIALS, type Scenario } from "@/lib/scenario"

const FLOW_WINDOW = 5 // cm/s: tests shown on the oxygen curve
const O2_WINDOW = 1.5 // points: tests shown on the flow curve
const one = (n: number) => Math.round(n * 10) / 10
const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

function curveAlong(
  scenario: Scenario,
  shape: string,
  key: "o2Percent" | "flowCmS",
  from: number,
  to: number,
  step: number
) {
  const points = []
  for (let v = from; v <= to + 1e-9; v += step) {
    const s = { ...scenario, [key]: v }
    const [low, high] = likelyRange(s, shape)
    points.push({ x: v, p: burnProbability(s, shape), low, high })
  }
  return points
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
  const dominant = model.solids.dominant_shape[scenario.material] ?? shapes[0]
  // The shape resets to the most flown one when the material changes
  const [choice, setChoice] = React.useState({ material: "", shape: "" })
  const shape =
    choice.material === scenario.material && shapes.includes(choice.shape)
      ? choice.shape
      : dominant
  const ofShape = ofMaterial.filter((t) => (t.geometry ?? "unknown") === shape)

  const o2Top = Math.max(36, Math.ceil(scenario.o2Percent + 2))
  const byOxygen = curveAlong(scenario, shape, "o2Percent", 12, o2Top, 0.5)
  const byFlow = curveAlong(scenario, shape, "flowCmS", 0, 50, 1)
  const nearFlow = ofShape.filter(
    (t) => Math.abs(t.flow_cm_s! - scenario.flowCmS) <= FLOW_WINDOW
  )
  const nearO2 = ofShape.filter(
    (t) => Math.abs(t.o2_percent! - scenario.o2Percent) <= O2_WINDOW
  )

  // Habitat oxygen levels as references; yours drawn strong (merged when they coincide)
  const o2Markers: Marker[] = [
    ...HABITATS.filter(
      (h) => Math.abs(h.o2Percent - scenario.o2Percent) > 0.4
    ).map((h) => ({ x: h.o2Percent, label: h.label })),
    {
      x: scenario.o2Percent,
      label: `You: ${scenario.o2Percent} %`,
      strong: true,
    },
  ]

  const burned = ofShape.filter((t) => t.sustained)
  const out = ofShape.filter((t) => !t.sustained)
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
      <PageHeader title="Flammability map" />
      <ScenarioBar />
      <div className="flex flex-col gap-4 p-4 md:p-8">
        {ofMaterial.length === 0 ? (
          <Card>
            <CardContent>
              <NothingFound
                icon={FlaskConicalIcon}
                title={`No flight test of ${material}`}
                reason="No test of this material has both an oxygen level and an air flow recorded."
              />
            </CardContent>
          </Card>
        ) : (
          <>
            <Card>
              <CardHeader>
                <CardTitle>
                  {material}, {shape}: {ofShape.length} flight tests
                </CardTitle>
                <CardDescription>
                  Curves: the model at {scenario.pressureAtm} atm. Dots: flight
                  tests of {material} {shape}s, all near 1 atm.
                </CardDescription>
                {shapes.length > 1 && (
                  <CardAction>
                    <ToggleGroup
                      type="single"
                      variant="outline"
                      size="sm"
                      value={shape}
                      onValueChange={(v) =>
                        v &&
                        setChoice({ material: scenario.material, shape: v })
                      }
                      className="flex-wrap"
                      aria-label="Sample shape"
                    >
                      {shapes.map((s) => (
                        <ToggleGroupItem key={s} value={s}>
                          {capital(s)}
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                  </CardAction>
                )}
              </CardHeader>
              {(lowestBurning || highestOut) && (
                <CardContent className="grid gap-4 sm:grid-cols-2">
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
                </CardContent>
              )}
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Chance a flame keeps burning, by oxygen</CardTitle>
                <CardDescription>
                  At {scenario.flowCmS} cm/s. Dots: {nearFlow.length} tests
                  flown at {Math.max(0, scenario.flowCmS - FLOW_WINDOW)} to{" "}
                  {scenario.flowCmS + FLOW_WINDOW} cm/s.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ChanceCurve
                  label="Oxygen"
                  unit="% O2"
                  domain={[12, o2Top]}
                  ticks={Array.from(
                    { length: Math.floor((o2Top - 12) / 4) + 1 },
                    (_, i) => 12 + 4 * i
                  )}
                  curve={byOxygen}
                  tests={nearFlow}
                  valueOf={(t) => t.o2_percent!}
                  binWidth={1}
                  markers={o2Markers}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Chance a flame keeps burning, by air flow</CardTitle>
                <CardDescription>
                  At {scenario.o2Percent} % O2. Dots: {nearO2.length} tests
                  flown at {one(scenario.o2Percent - O2_WINDOW)} to{" "}
                  {one(scenario.o2Percent + O2_WINDOW)} % O2.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ChanceCurve
                  label="Air flow past the sample"
                  unit="cm/s"
                  domain={[0, 50]}
                  ticks={[0, 10, 20, 30, 40, 50]}
                  curve={byFlow}
                  tests={nearO2}
                  valueOf={(t) => t.flow_cm_s!}
                  binWidth={2}
                  markers={[
                    {
                      x: scenario.flowCmS,
                      label: `You: ${scenario.flowCmS} cm/s`,
                      strong: true,
                    },
                  ]}
                />
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </>
  )
}
