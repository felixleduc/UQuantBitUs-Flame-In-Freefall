import { z } from "zod"

import findingsJson from "@/data/findings.json"
import testsJson from "@/data/tests.json"

// Written by src/export_dashboard_data.py from data/processed/: validated once here.

const Test = z.object({
  psi_id: z.string(),
  investigation: z.string(),
  test_id: z.coerce.string(),
  date: z.coerce.string().optional(),
  material: z.string().optional(),
  material_family: z.string().optional(),
  geometry: z.string().optional(),
  thickness_mm: z.number().optional(),
  diameter_mm: z.number().optional(),
  o2_percent: z.number().optional(),
  pressure_atm: z.number().optional(),
  flow_cm_s: z.number().optional(),
  flow_direction: z.string().optional(),
  outcome: z.string().optional(),
  burn_time_s: z.number().optional(),
  spread_rate_mm_s: z.number().optional(),
  notes: z.string().optional(),
  sustained: z.boolean().nullable().optional(),
})

const Finding = z.object({
  psi_id: z.string(),
  field: z.string(),
  value: z.string(),
  quote: z.string(),
  file: z.string(),
  page: z.coerce.string().optional(),
  acronym: z.string(),
  group: z.string(),
  type: z.string(), // finding type, set in src/export_dashboard_data.py
  url: z.string(),
})

export type Test = z.infer<typeof Test>
export type Finding = z.infer<typeof Finding>

export const tests: Test[] = z.array(Test).parse(testsJson)
export const findings: Finding[] = z.array(Finding).parse(findingsJson)
