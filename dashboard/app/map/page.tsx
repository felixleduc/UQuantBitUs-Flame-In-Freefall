"use client"

import * as React from "react"
import { FlaskConicalIcon } from "lucide-react"

import {
  FlammabilityHeatmap,
  heatColor,
} from "@/components/flammability-heatmap"
import { InfoHint } from "@/components/info-hint"
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
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { Test } from "@/lib/data"
import { flownTests } from "@/lib/evidence"
import { model } from "@/lib/model"
import { MATERIALS } from "@/lib/scenario"

const one = (n: number) => Math.round(n * 10) / 10

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

function Swatch({ children }: { children: React.ReactNode }) {
  return <span className="flex items-center gap-1.5">{children}</span>
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
  const modelShape =
    shape === "all" ? model.solids.dominant_shape[scenario.material] : shape

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

  return (
    <>
      <PageHeader title="Flammability map" />
      <ScenarioBar />
      <div className="flex flex-col gap-4 p-4 md:p-8">
        <Card className="min-w-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-1">
              {material}: chance a flame keeps burning
              <InfoHint>
                Colour: the model at {scenario.pressureAtm} atm, for a{" "}
                {modelShape} sample. Dots: the real flight tests, all flown near
                1 atm.
              </InfoHint>
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
          <CardContent className="flex flex-col gap-6">
            {flown.length === 0 ? (
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

                <FlammabilityHeatmap
                  scenario={scenario}
                  shape={modelShape}
                  tests={flown}
                />

                <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
                  <Swatch>
                    <span
                      className="h-3 w-16 rounded-sm"
                      style={{
                        background: `linear-gradient(to right, ${heatColor(0)}, ${heatColor(0.5)}, ${heatColor(1)})`,
                      }}
                    />
                    Goes out to keeps burning (model)
                  </Swatch>
                  <Swatch>
                    <span className="w-5 border-t-2 border-dashed border-foreground" />
                    50 % line
                  </Swatch>
                  <Swatch>
                    <span className="size-2.5 rounded-full bg-foreground" />
                    Test: kept burning
                  </Swatch>
                  <Swatch>
                    <span className="size-2.5 rounded-full border-[1.5px] border-foreground bg-background" />
                    Test: went out
                  </Swatch>
                  <Swatch>
                    <span className="size-3.5 rounded-full border-[2.5px] border-foreground" />
                    Your scenario
                  </Swatch>
                  <Swatch>
                    <span className="h-3 w-5 border border-dashed border-foreground/60" />
                    Oxygen range flown with solids
                  </Swatch>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
