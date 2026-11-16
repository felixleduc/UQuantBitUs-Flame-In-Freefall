import { z } from "zod"

import flightTestsJson from "@/data/flight-tests.json"

// The tests the model learned from, written by ML.py with their label (1: the flame kept
// burning). Imported only by the pages that list or count them, to keep the others light.

const FlightTest = z.object({
  psi_id: z.string(),
  investigation: z.string(),
  test_id: z.coerce.string(),
  fuel_type: z.string(),
  material_family: z.string().optional(),
  geometry: z.string().optional(),
  o2_percent: z.number(),
  pressure_atm: z.number(),
  flow_cm_s: z.number().optional(),
  outcome: z.string().optional(),
  kept_burning: z.number(),
})

export type FlightTest = z.infer<typeof FlightTest> & { sustained: boolean }

export const flightTests: FlightTest[] = z
  .array(FlightTest)
  .parse(flightTestsJson)
  .map((t) => ({ ...t, sustained: t.kept_burning === 1 }))
