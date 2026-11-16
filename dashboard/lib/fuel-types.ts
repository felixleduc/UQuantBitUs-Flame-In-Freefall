// Names of the kinds of flight test, kept apart from the test list so that importing
// them does not load it.

export const FUEL_TYPES: Record<string, string> = {
  solid: "Solids",
  "gas burner": "Gas burners",
  "gas jet": "Gas jets",
  droplet: "Droplets",
}

// Which kind of test each investigation flew, for filtering findings the same way
export const AREAS: Record<string, string> = {
  ...FUEL_TYPES,
  smoke: "Smoke detection",
}
const AREA_OF: Record<string, string> = {
  "PSI-98": "solid",
  "PSI-99": "solid",
  "PSI-100": "solid",
  "PSI-25": "solid",
  "PSI-26": "solid",
  "PSI-20": "gas burner",
  "PSI-23": "gas burner",
  "PSI-10": "gas jet",
  "PSI-159": "gas jet",
  "PSI-21": "gas jet",
  "PSI-22": "gas jet",
  "PSI-106": "gas jet",
  "PSI-107": "gas jet",
  "PSI-69": "droplet",
  "PSI-68": "droplet",
  "PSI-39": "droplet",
  "PSI-102": "smoke",
  "PSI-101": "smoke",
  "PSI-47": "smoke",
}
export const areaOf = (psiId: string) => AREA_OF[psiId] ?? "other"
