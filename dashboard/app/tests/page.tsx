"use client"

import * as React from "react"
import { SearchIcon } from "lucide-react"
import { useSearchParams } from "next/navigation"

import { PageHeader } from "@/components/page-header"
import { TestsTable } from "@/components/tests-table"
import { Card, CardContent } from "@/components/ui/card"
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
import { tests } from "@/lib/data"
import { MATERIALS } from "@/lib/scenario"

const OUTCOMES = {
  all: "All",
  burned: "Kept burning",
  out: "Went out",
} as const

export default function TestsPage() {
  // useSearchParams needs a Suspense boundary on a statically built page
  return (
    <React.Suspense>
      <Tests />
    </React.Suspense>
  )
}

function Tests() {
  const linked = useSearchParams().get("material") ?? "all"
  const [material, setMaterial] = React.useState(
    linked in MATERIALS ? linked : "all"
  )
  const [query, setQuery] = React.useState("")
  const [outcome, setOutcome] = React.useState<keyof typeof OUTCOMES>("all")

  const shown = tests.filter((t) => {
    if (material !== "all" && t.material_family !== material) return false
    if (outcome === "burned" && t.sustained !== true) return false
    if (outcome === "out" && t.sustained !== false) return false
    const text =
      `${t.investigation} ${t.test_id} ${t.material ?? ""} ${t.outcome ?? ""}`.toLowerCase()
    return text.includes(query.toLowerCase())
  })

  return (
    <>
      <PageHeader title="Space tests" />
      <div className="flex flex-col gap-4 p-4 md:p-8">
        <div className="flex flex-wrap items-center gap-3">
          <Select value={material} onValueChange={setMaterial}>
            <SelectTrigger size="sm" className="w-56" aria-label="Material">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="all">All materials</SelectItem>
                {Object.entries(MATERIALS).map(([id, m]) => (
                  <SelectItem key={id} value={id}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
          <InputGroup className="max-w-xs">
            <InputGroupInput
              placeholder="Search material, test, outcome"
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
            {Object.entries(OUTCOMES).map(([id, label]) => (
              <ToggleGroupItem key={id} value={id}>
                {label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <span className="ml-auto text-sm text-muted-foreground">
            {shown.length} tests
          </span>
        </div>
        <Card>
          <CardContent>
            <TestsTable tests={shown} empty="No test matches these filters." />
          </CardContent>
        </Card>
      </div>
    </>
  )
}
