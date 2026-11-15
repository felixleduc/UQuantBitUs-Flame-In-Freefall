"use client"

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { BookOpenIcon, DownloadIcon, InfoIcon } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { InfoHint } from "@/components/info-hint"
import { PageHeader } from "@/components/page-header"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { tests } from "@/lib/data"
import { MATERIALS } from "@/lib/scenario"

// Stacked by outcome: two series, legend-free because the description names them.
const config = {
  burned: { label: "Kept burning", color: "var(--chart-2)" },
  out: { label: "Went out", color: "var(--chart-1)" },
} satisfies ChartConfig

const rows = Object.entries(MATERIALS)
  .map(([id, m]) => {
    const flown = tests.filter((t) => t.material_family === id)
    return {
      id,
      label: m.label,
      material: `${m.label} (${flown.length})`,
      burned: flown.filter((t) => t.sustained === true).length,
      out: flown.filter((t) => t.sustained === false).length,
      total: flown.length,
    }
  })
  .sort((a, b) => b.total - a.total)

// Stated from the data so the warning follows the export
const THIN = 12
const thin = rows.filter((r) => r.total < THIN).map((r) => r.label)
const lowestPressure = Math.min(...tests.map((t) => t.pressure_atm ?? Infinity))

const REPO = "https://github.com/felixleduc/UQuantBitUs-Flame-In-Freefall"
const idOf = (material: string) => rows.find((r) => r.material === material)?.id ?? ""

// Material names on the axis are links to that material's flight tests
function MaterialTick({ x, y, payload }: { x?: number | string; y?: number | string; payload?: { value: string } }) {
  const id = idOf(payload?.value ?? "")
  return (
    <Link href={`/tests?material=${encodeURIComponent(id)}`}>
      <text x={x} y={y} dy={4} textAnchor="end" className="fill-foreground text-xs underline-offset-2 hover:underline">
        {payload?.value}
      </text>
    </Link>
  )
}

export default function CoveragePage() {
  const router = useRouter()
  const openTests = (id: string) => router.push(`/tests?material=${encodeURIComponent(id)}`)
  return (
    <>
      <PageHeader title="Coverage" />
      <div className="flex flex-col gap-4 p-4 md:p-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1">
              Flight tests per material
              <InfoHint>Tests with no stated outcome are left out.</InfoHint>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ChartContainer config={config} className="aspect-auto h-72 w-full">
              <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 40 }}>
                <CartesianGrid horizontal={false} />
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="material"
                  width={190}
                  tickLine={false}
                  axisLine={false}
                  tick={MaterialTick}
                />
                <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
                <ChartLegend verticalAlign="top" content={<ChartLegendContent />} />
                <Bar dataKey="burned" stackId="a" fill="var(--color-burned)" radius={[4, 0, 0, 4]} className="cursor-pointer" onClick={(d) => openTests(d.payload.id)} />
                <Bar dataKey="out" stackId="a" fill="var(--color-out)" radius={[0, 4, 4, 0]} className="cursor-pointer" onClick={(d) => openTests(d.payload.id)} />
              </BarChart>
            </ChartContainer>
          </CardContent>
          <CardFooter className="flex-wrap justify-between gap-2">
            <span className="text-xs text-muted-foreground">
              Click a material to see its tests.
            </span>
            <span className="flex flex-wrap gap-1">
              <Button asChild variant="ghost" size="sm">
                <a href={`${REPO}/blob/master/data/processed/tests.csv`} target="_blank" rel="noreferrer">
                  <DownloadIcon data-icon="inline-start" />
                  All tests (tests.csv)
                </a>
              </Button>
              <Button asChild variant="ghost" size="sm">
                <a href={`${REPO}#testscsv`} target="_blank" rel="noreferrer">
                  <BookOpenIcon data-icon="inline-start" />
                  What each column means
                </a>
              </Button>
            </span>
          </CardFooter>
        </Card>
        <Alert>
          <InfoIcon />
          <AlertTitle>Thin evidence</AlertTitle>
          <AlertDescription>
            {thin.join(", ")} have fewer than {THIN} flight tests each, and no solid was flown below {lowestPressure} atm.
            Predictions for low-pressure habitats are extrapolated.
          </AlertDescription>
        </Alert>
      </div>
    </>
  )
}
