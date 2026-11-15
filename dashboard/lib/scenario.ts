// What the dashboard asks about: a material in a habitat atmosphere. Stable when the model changes.

export type Scenario = {
  material: string // a key of MATERIALS (the `material_family` of tests.json)
  o2Percent: number
  pressureAtm: number
  flowCmS: number
}

export const MATERIALS: Record<string, { label: string; keywords: RegExp }> = {
  PMMA: { label: "PMMA (acrylic)", keywords: /pmma|acrylic|rod/i },
  "SIBAL cotton-fiberglass fabric": {
    label: "Cotton-fiberglass fabric",
    keywords: /sibal|fabric|cotton/i,
  },
  Nomex: { label: "Nomex", keywords: /nomex/i },
  Ultem: { label: "Ultem", keywords: /ultem/i },
  silicone: { label: "Silicone", keywords: /silicone/i },
  "paraffin wax": { label: "Paraffin wax", keywords: /wax|candle|paraffin/i },
  "Japan wax": { label: "Japan wax", keywords: /wax|candle/i },
}

export type Habitat = {
  id: string
  label: string
  detail: string // the atmosphere, in numbers
  use: string // where NASA uses it
  phrase: string // completes "PMMA keeps burning ..."
} & Omit<Scenario, "material">

// Atmospheres NASA uses or has proposed; ventilation is a typical cabin value.
export const HABITATS: Habitat[] = [
  {
    id: "iss",
    phrase: "on the ISS",
    label: "ISS cabin",
    detail: "21 % O2 at 1 atm (14.7 psi)",
    use: "Sea-level air, as on the ISS today",
    o2Percent: 21,
    pressureAtm: 1,
    flowCmS: 10,
  },
  {
    id: "pre-eva",
    phrase: "in the pre-spacewalk atmosphere",
    label: "Pre-spacewalk cabin",
    detail: "26.5 % O2 at 0.69 atm (10.2 psi)",
    use: "Space Shuttle cabin before spacewalks",
    o2Percent: 26.5,
    pressureAtm: 0.69,
    flowCmS: 10,
  },
  {
    id: "exploration",
    phrase: "in an exploration habitat",
    label: "Exploration habitat",
    detail: "34 % O2 at 0.56 atm (8.2 psi)",
    use: "NASA's recommended Moon and Mars habitat atmosphere",
    o2Percent: 34,
    pressureAtm: 0.56,
    flowCmS: 10,
  },
]

export type Verdict = "burns" | "borderline" | "self-extinguishes"

export function verdictOf(probability: number): Verdict {
  if (probability >= 0.7) return "burns"
  if (probability >= 0.3) return "borderline"
  return "self-extinguishes"
}

export const pct = (probability: number) => Math.round(probability * 100)
