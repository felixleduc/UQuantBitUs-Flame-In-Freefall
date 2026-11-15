"use client"

import * as React from "react"
import { useSearchParams } from "next/navigation"

import { FindingCard } from "@/components/finding-card"
import { PageHeader } from "@/components/page-header"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { findings } from "@/lib/data"
import { findingsAbout } from "@/lib/evidence"
import { MATERIALS } from "@/lib/scenario"

// Most useful for habitat fire safety first; how the tests were run last.
const ORDER = [
  "Oxygen and pressure limits",
  "Ignition",
  "Flame spread",
  "Extinction",
  "Ventilation and flow",
  "Suppression",
  "Material behavior",
  "Smoke and detection",
  "Cool flames",
  "Flame behavior",
  "Test setup",
]
const rank = (type: string) => {
  const i = ORDER.indexOf(type)
  return i === -1 ? ORDER.length : i
}

const MATERIAL_IDS = Object.keys(MATERIALS).filter(
  (id) => findingsAbout(id).length > 0
)

export default function FindingsPage() {
  // useSearchParams needs a Suspense boundary on a statically built page
  return (
    <React.Suspense>
      <Findings />
    </React.Suspense>
  )
}

function Findings() {
  const params = useSearchParams()
  const linked = params.get("material") ?? "all"
  const [material, setMaterial] = React.useState(
    MATERIAL_IDS.includes(linked) ? linked : "all"
  )
  const [type, setType] = React.useState("all")

  const ofMaterial = material === "all" ? findings : findingsAbout(material)
  const counts = ofMaterial.reduce<Record<string, number>>((acc, f) => {
    acc[f.type] = (acc[f.type] ?? 0) + 1
    return acc
  }, {})
  const types = Object.keys(counts).sort((a, b) => rank(a) - rank(b))
  const shown = ofMaterial
    .filter((f) => type === "all" || f.type === type)
    .sort((a, b) => rank(a.type) - rank(b.type))

  return (
    <>
      <PageHeader title="Findings" />
      <div className="flex flex-col gap-4 p-4 md:p-8">
        <div className="flex flex-wrap items-start gap-3">
          <Select
            value={material}
            onValueChange={(v) => {
              setMaterial(v)
              setType("all")
            }}
          >
            <SelectTrigger size="sm" className="w-56" aria-label="Material">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="all">All materials</SelectItem>
                {MATERIAL_IDS.map((id) => (
                  <SelectItem key={id} value={id}>
                    {MATERIALS[id].label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={type}
            onValueChange={(v) => v && setType(v)}
            className="flex-wrap"
            aria-label="Finding type"
          >
            <ToggleGroupItem value="all">
              All
              <span className="text-muted-foreground tabular-nums">
                {ofMaterial.length}
              </span>
            </ToggleGroupItem>
            {types.map((t) => (
              <ToggleGroupItem key={t} value={t}>
                {t}
                <span className="text-muted-foreground tabular-nums">
                  {counts[t]}
                </span>
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {shown.map((f) => (
            <FindingCard key={`${f.psi_id}-${f.quote}`} finding={f} />
          ))}
        </div>
      </div>
    </>
  )
}
