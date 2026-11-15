import { z } from "zod"

import modelJson from "@/data/model.json"
import type { Scenario } from "@/lib/scenario"

// Written by ML.py (repository root): a logistic regression trained on the solid-material
// flight tests, evaluated on a grid of oxygen and air flow for each material, with the
// 5th to 95th percentile of 200 bootstrap refits as the likely range. Validated once here.

const Grid = z.array(z.array(z.number()))
const Model = z.object({
  trained_on: z.number(),
  kept_burning_share: z.number(),
  metrics: z.object({
    balanced_accuracy: z.number(),
    roc_auc: z.number(),
    brier: z.number(),
    baseline_brier: z.number(),
  }),
  pressure_range_atm: z.tuple([z.number(), z.number()]),
  o2: z.array(z.number()),
  flow: z.array(z.number()),
  materials: z.record(
    z.string(),
    z.object({
      tests: z.number(),
      geometry: z.string(),
      p: Grid,
      low: Grid,
      high: Grid,
    })
  ),
})

export const model = Model.parse(modelJson)

// Position of a value on a grid axis: index of the cell and fraction inside it
function locate(axis: number[], value: number): [number, number] {
  const v = Math.min(Math.max(value, axis[0]), axis[axis.length - 1])
  const i = Math.min(
    axis.findLastIndex((a) => a <= v),
    axis.length - 2
  )
  return [i, (v - axis[i]) / (axis[i + 1] - axis[i])]
}

// Bilinear interpolation between the four grid points around (O2, flow).
// Pressure is not an input: every solid was flown near 1 atm.
function read(grid: number[][], s: Scenario): number {
  const [i, a] = locate(model.o2, s.o2Percent)
  const [j, b] = locate(model.flow, s.flowCmS)
  return (
    grid[i][j] * (1 - a) * (1 - b) +
    grid[i + 1][j] * a * (1 - b) +
    grid[i][j + 1] * (1 - a) * b +
    grid[i + 1][j + 1] * a * b
  )
}

const gridsOf = (material: string) =>
  model.materials[material] ?? model.materials.PMMA

export function burnProbability(s: Scenario): number {
  return read(gridsOf(s.material).p, s)
}

export function likelyRange(s: Scenario): readonly [number, number] {
  const g = gridsOf(s.material)
  return [read(g.low, s), read(g.high, s)] as const
}

export type Lever = {
  id: string
  label: string
  change: string
  probability: number
  delta: number
}

// Changes the model can judge: oxygen, ventilation within the flown range, material.
// Pressure is left out because the flight data does not vary it.
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
