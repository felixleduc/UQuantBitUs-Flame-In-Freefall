"use client"

import * as React from "react"

import { HABITATS, type Scenario } from "@/lib/scenario"

type ScenarioContext = {
  scenario: Scenario
  habitatId: string // a preset id, or "custom" once a slider moves
  setMaterial: (material: string) => void
  setHabitat: (id: string) => void
  setValue: (
    key: "o2Percent" | "pressureAtm" | "flowCmS",
    value: number
  ) => void
}

const Context = React.createContext<ScenarioContext | null>(null)

// The scenario is shared by every page, so moving between views keeps the same question.
export function ScenarioProvider({ children }: { children: React.ReactNode }) {
  const iss = HABITATS[0]
  const [habitatId, setHabitatId] = React.useState(iss.id)
  const [scenario, setScenario] = React.useState<Scenario>({
    material: "PMMA",
    o2Percent: iss.o2Percent,
    pressureAtm: iss.pressureAtm,
    flowCmS: iss.flowCmS,
  })

  const value = React.useMemo<ScenarioContext>(
    () => ({
      scenario,
      habitatId,
      setMaterial: (material) => setScenario((s) => ({ ...s, material })),
      setHabitat: (id) => {
        const habitat = HABITATS.find((h) => h.id === id)
        if (!habitat) return
        setHabitatId(id)
        setScenario((s) => ({
          ...s,
          o2Percent: habitat.o2Percent,
          pressureAtm: habitat.pressureAtm,
          flowCmS: habitat.flowCmS,
        }))
      },
      setValue: (key, v) => {
        setHabitatId("custom")
        setScenario((s) => ({ ...s, [key]: v }))
      },
    }),
    [scenario, habitatId]
  )

  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useScenario() {
  const context = React.useContext(Context)
  if (!context)
    throw new Error("useScenario must be used inside ScenarioProvider")
  return context
}
