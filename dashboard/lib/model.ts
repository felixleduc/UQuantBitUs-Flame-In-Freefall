import { z } from "zod"

import modelJson from "@/data/model.json"
import type { Scenario } from "@/lib/scenario"

// Written by ML.py (repository root): a logistic regression trained on every flight test with
// a flame outcome. For a solid, the chance a flame keeps burning is
//   logit = intercept + condensed group + material + sample shape
//           + O2 slope * (O2 - 21) / 3 + pressure slope * ln(pressure)
//           + flow1 * ln(1 + flow) + flow2 * ln(1 + flow)^2
// The pressure slope comes from BRE, NASA's gas-burner emulator of a burning solid, flown at
// 0.54 to 1 atm. Validated once here.

const Weights = z.record(z.string(), z.number())
const Score = z.object({ roc_auc: z.number(), brier: z.number() })
const Model = z.object({
  trained_on: z.number(),
  tests_by_type: z.record(z.string(), z.number()),
  metrics: z.object({
    solids_pooled: Score,
    solids_only_model: Score,
    solids_baseline_brier: z.number(),
  }),
  o2_center: z.number(),
  o2_scale: z.number(),
  solids: z.object({
    tests: z.number(),
    o2_range: z.tuple([z.number(), z.number()]),
    pressure_range_atm: z.tuple([z.number(), z.number()]),
    dominant_shape: z.record(z.string(), z.string()),
  }),
  pressure_source: z.object({
    investigations: z.array(z.string()),
    pressure_range_atm: z.tuple([z.number(), z.number()]),
  }),
  coefficients: Weights,
  refits: z.array(Weights),
})

export const model = Model.parse(modelJson)

const shapeOf = (s: Scenario, shape?: string) =>
  shape ?? model.solids.dominant_shape[s.material] ?? "sphere"

function chance(w: Record<string, number>, s: Scenario, shape?: string) {
  const flow = Math.log1p(Math.max(0, s.flowCmS))
  const logit =
    w.intercept +
    (w["group:condensed"] ?? 0) +
    (w[`solid:${s.material}`] ?? 0) +
    (w[`shape:${shapeOf(s, shape)}`] ?? 0) +
    w["o2:solid"] * ((s.o2Percent - model.o2_center) / model.o2_scale) +
    w["lnp:condensed"] * Math.log(Math.max(s.pressureAtm, 0.05)) +
    w.flow1 * flow +
    w.flow2 * flow * flow
  return 1 / (1 + Math.exp(-logit))
}

// `shape` defaults to the shape the material was flown in most
export function burnProbability(s: Scenario, shape?: string): number {
  return chance(model.coefficients, s, shape)
}

// 5th to 95th percentile of the 200 refits on resampled data
export function likelyRange(
  s: Scenario,
  shape?: string
): readonly [number, number] {
  const all = model.refits.map((w) => chance(w, s, shape)).sort((a, b) => a - b)
  const at = (q: number) => all[Math.round(q * (all.length - 1))]
  return [at(0.05), at(0.95)] as const
}

export type Lever = {
  id: string
  label: string
  change: string
  probability: number
  delta: number
}

// Changes the model can judge. Stopping ventilation is left out: tests are filed under the
// flow at ignition, so the data cannot tell what happens when the fans stop mid-fire.
export function safetyLevers(s: Scenario): Lever[] {
  const base = burnProbability(s)
  const options: {
    id: string
    label: string
    change: string
    next: Scenario
  }[] = [
    {
      id: "o2-2",
      label: "Lower oxygen",
      change: "−2 points of O2",
      next: { ...s, o2Percent: s.o2Percent - 2 },
    },
    {
      id: "o2-4",
      label: "Lower oxygen more",
      change: "−4 points of O2",
      next: { ...s, o2Percent: s.o2Percent - 4 },
    },
    {
      id: "pressure",
      label: "Raise pressure",
      change: "+0.1 atm, same O2 %",
      next: { ...s, pressureAtm: s.pressureAtm + 0.1 },
    },
    {
      id: "fan-down",
      label: "Less ventilation",
      change: "−5 cm/s",
      next: { ...s, flowCmS: Math.max(0, s.flowCmS - 5) },
    },
    {
      id: "fan-up",
      label: "More ventilation",
      change: "+10 cm/s",
      next: { ...s, flowCmS: s.flowCmS + 10 },
    },
    {
      id: "nomex",
      label: "Switch to Nomex",
      change: "same atmosphere",
      next: { ...s, material: "Nomex" },
    },
  ]
  return options
    .filter((o) => !(o.id === "nomex" && s.material === "Nomex"))
    .map((o) => {
      const probability = burnProbability(o.next)
      return {
        id: o.id,
        label: o.label,
        change: o.change,
        probability,
        delta: probability - base,
      }
    })
    .sort((a, b) => a.delta - b.delta)
}
