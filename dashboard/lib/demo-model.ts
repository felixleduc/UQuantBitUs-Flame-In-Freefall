// DEMO MODEL: invented coefficients so the screens can be built before the real model exists.
// The trained model replaces this file: same exports, `burnProbability` returns 0..1.

import type { Scenario } from "@/lib/scenario"

const PARAMS: Record<string, { limitO2: number; blowoffCmS: number }> = {
  PMMA: { limitO2: 16.5, blowoffCmS: 35 },
  "SIBAL cotton-fiberglass fabric": { limitO2: 17, blowoffCmS: 45 },
  Nomex: { limitO2: 24, blowoffCmS: 25 },
  Ultem: { limitO2: 23, blowoffCmS: 25 },
  silicone: { limitO2: 22, blowoffCmS: 30 },
  "paraffin wax": { limitO2: 18, blowoffCmS: 30 },
  "Japan wax": { limitO2: 18.5, blowoffCmS: 30 },
}

const sigmoid = (x: number) => 1 / (1 + Math.exp(-x))

export function burnProbability({
  material,
  o2Percent,
  pressureAtm,
  flowCmS,
}: Scenario): number {
  const m = PARAMS[material] ?? PARAMS.PMMA
  const oxygen = 0.25 * (o2Percent - m.limitO2)
  const pressure = 3 * Math.log(Math.max(pressureAtm, 0.05))
  const quench = 3 * Math.exp(-flowCmS / 2) // little flow in microgravity starves the flame
  const blowoff = Math.max(0, flowCmS - m.blowoffCmS) / 6
  return sigmoid(oxygen + pressure - quench - blowoff)
}

export type Lever = {
  id: string
  label: string
  change: string
  probability: number
  delta: number
}

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
      label: "Lower pressure",
      change: "−0.1 atm, same O2 %",
      next: { ...s, pressureAtm: Math.max(0.2, s.pressureAtm - 0.1) },
    },
    {
      id: "fan-off",
      label: "Stop ventilation",
      change: "flow to 1 cm/s",
      next: { ...s, flowCmS: 1 },
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
