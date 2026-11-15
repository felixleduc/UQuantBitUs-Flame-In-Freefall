import { findings, tests, type Test } from "@/lib/data"
import { MATERIALS, type Scenario } from "@/lib/scenario"

// Flight tests of a material with a known oxygen level and a known outcome.
export function flownTests(material: string): Test[] {
  return tests.filter(
    (t) =>
      t.material_family === material &&
      t.o2_percent !== undefined &&
      t.sustained != null
  )
}

// Real tests that resemble the scenario: nearest O2, then nearest flow.
export function closestTests(s: Scenario, count = 5): Test[] {
  return flownTests(s.material)
    .map((t) => ({
      t,
      distance:
        Math.abs(t.o2_percent! - s.o2Percent) +
        0.2 * Math.abs((t.flow_cm_s ?? s.flowCmS) - s.flowCmS),
    }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, count)
    .map(({ t }) => t)
}

export type Evidence = {
  level: "strong" | "limited" | "extrapolated"
  similar: number
  reason: string
}

// How much flight data stands near the scenario: same material, O2 within 2 points, pressure flown.
export function evidenceFor(s: Scenario): Evidence {
  const flown = flownTests(s.material)
  const near = flown.filter((t) => Math.abs(t.o2_percent! - s.o2Percent) <= 2)
  const similar = near.length
  const name = MATERIALS[s.material]?.label ?? s.material
  const lowest = Math.min(...tests.map((t) => t.pressure_atm ?? Infinity))
  const band = `${Math.round(s.o2Percent - 2)} to ${Math.round(s.o2Percent + 2)} % O2`
  if (s.pressureAtm < lowest - 0.02)
    return {
      level: "extrapolated",
      similar,
      reason: `No solid was flown below ${lowest} atm: this is extrapolated beyond the flight data.`,
    }
  if (similar === 0)
    return {
      level: "extrapolated",
      similar,
      reason: `No flight test of ${name} between ${band}: this is extrapolated.`,
    }
  return {
    level: similar < 10 ? "limited" : "strong",
    similar,
    reason: `Based on ${similar} flight test${similar > 1 ? "s" : ""} of ${name} between ${band}.`,
  }
}

// Demo uncertainty: the range widens as the flight evidence near the scenario thins out.
const MARGIN: Record<Evidence["level"], number> = {
  strong: 0.06,
  limited: 0.12,
  extrapolated: 0.25,
}

export function likelyRange(probability: number, level: Evidence["level"]) {
  const m = MARGIN[level]
  return [Math.max(0, probability - m), Math.min(1, probability + m)] as const
}

// Finding types an engineer sizing a habitat needs next to the prediction
export const LIMIT_TYPES = [
  "Oxygen and pressure limits",
  "Ignition",
  "Flame spread",
  "Extinction",
  "Ventilation and flow",
]

// Every report finding that names this material, limits first.
export function findingsAbout(material: string) {
  const pattern = MATERIALS[material]?.keywords
  if (!pattern) return []
  const limitFirst = (type: string) =>
    LIMIT_TYPES.includes(type) ? LIMIT_TYPES.indexOf(type) : LIMIT_TYPES.length
  return findings
    .filter(
      (f) => f.type !== "Test setup" && pattern.test(`${f.value} ${f.quote}`)
    )
    .sort((a, b) => limitFirst(a.type) - limitFirst(b.type))
}
