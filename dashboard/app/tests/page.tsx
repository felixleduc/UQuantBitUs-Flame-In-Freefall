"use client"

import * as React from "react"
import { SearchIcon } from "lucide-react"
import { useSearchParams } from "next/navigation"

import { PageHeader } from "@/components/page-header"
import { TestsTable } from "@/components/tests-table"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { flightTests } from "@/lib/flight-tests"
import { FUEL_TYPES } from "@/lib/fuel-types"
import { MATERIALS } from "@/lib/scenario"

const OUTCOMES = {
  all: "All",
  burned: "Kept burning",
  out: "Went out",
} as const
const PAGE = 100

const label = (material: string) => MATERIALS[material]?.label ?? material

export default function TestsPage() {
  // useSearchParams needs a Suspense boundary on a statically built page
  return (
    <React.Suspense>
      <Tests />
    </React.Suspense>
  )
}

function Tests() {
  const params = useSearchParams()
  const linkedMaterial = params.get("material")
  const linkedType = params.get("type") ?? (linkedMaterial ? "solid" : "all")
  const [type, setType] = React.useState(
    linkedType in FUEL_TYPES ? linkedType : "all"
  )
  const [material, setMaterial] = React.useState(linkedMaterial ?? "all")
  const [query, setQuery] = React.useState("")
  const [outcome, setOutcome] = React.useState<keyof typeof OUTCOMES>("all")
  const [shownCount, setShownCount] = React.useState(PAGE)

  const ofType = flightTests.filter(
    (t) => type === "all" || t.fuel_type === type
  )
  // Materials of the chosen type, most tested first
  const materials = Object.entries(
    ofType.reduce<Record<string, number>>((acc, t) => {
      const m = t.material_family ?? "unknown"
      acc[m] = (acc[m] ?? 0) + 1
      return acc
    }, {})
  ).sort((a, b) => b[1] - a[1])

  const shown = ofType.filter((t) => {
    if (material !== "all" && t.material_family !== material) return false
    if (outcome === "burned" && !t.sustained) return false
    if (outcome === "out" && t.sustained) return false
    const text =
      `${t.investigation} ${t.test_id} ${t.material_family ?? ""} ${t.outcome ?? ""}`.toLowerCase()
    return text.includes(query.toLowerCase())
  })

  return (
    <>
      <PageHeader title="Space tests" />
      <div className="flex flex-col gap-4 p-4 md:p-8">
        <div className="flex flex-wrap items-center gap-3">
          <Select
            value={type}
            onValueChange={(v) => {
              setType(v)
              setMaterial("all")
              setShownCount(PAGE)
            }}
          >
            <SelectTrigger size="sm" className="w-40" aria-label="Type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="all">All types</SelectItem>
                {Object.entries(FUEL_TYPES).map(([id, name]) => (
                  <SelectItem key={id} value={id}>
                    {name}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <Select
            value={material}
            onValueChange={(v) => {
              setMaterial(v)
              setShownCount(PAGE)
            }}
          >
            <SelectTrigger
              size="sm"
              className="w-56"
              aria-label="Fuel or material"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="all">All fuels and materials</SelectItem>
                {materials.map(([m, n]) => (
                  <SelectItem key={m} value={m}>
                    {label(m)} ({n})
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <InputGroup className="max-w-xs">
            <InputGroupInput
              placeholder="Search test, fuel, outcome"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <InputGroupAddon>
              <SearchIcon />
            </InputGroupAddon>
          </InputGroup>
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={outcome}
            onValueChange={(v) => v && setOutcome(v as keyof typeof OUTCOMES)}
          >
            {Object.entries(OUTCOMES).map(([id, name]) => (
              <ToggleGroupItem key={id} value={id}>
                {name}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <span className="ml-auto text-sm text-muted-foreground">
            {shown.length} of {flightTests.length} tests the model learned from
          </span>
        </div>
        <Card>
          <CardContent>
            <TestsTable
              tests={shown.slice(0, shownCount)}
              empty="No test matches these filters."
            />
          </CardContent>
          {shown.length > shownCount && (
            <CardFooter className="justify-center">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShownCount((n) => n + PAGE)}
              >
                Show {Math.min(PAGE, shown.length - shownCount)} more
              </Button>
            </CardFooter>
          )}
        </Card>
      </div>
    </>
  )
}
