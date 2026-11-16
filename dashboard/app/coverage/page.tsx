"use client"

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { BookOpenIcon, DownloadIcon, InfoIcon } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { InfoHint } from "@/components/info-hint"
import { PageHeader } from "@/components/page-header"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { flightTests } from "@/lib/flight-tests"
import { FUEL_TYPES } from "@/lib/fuel-types"
import { model } from "@/lib/model"
import { MATERIALS } from "@/lib/scenario"

const REPO = "https://github.com/felixleduc/UQuantBitUs-Flame-In-Freefall"
const span = (values: number[], digits: number) => {
  const r = (v: number) => Math.round(v * 10 ** digits) / 10 ** digits
  return `${r(Math.min(...values))} to ${r(Math.max(...values))}`
}

// What the model learned from, per fuel type
const byType = Object.entries(FUEL_TYPES).map(([id, name]) => {
  const ofType = flightTests.filter((t) => t.fuel_type === id)
  return {
    id,
    name,
    tests: ofType.length,
    kept: ofType.filter((t) => t.sustained).length,
    o2: span(ofType.map((t) => t.o2_percent), 0),
    pressure: span(ofType.map((t) => t.pressure_atm), 2),
    investigations: [...new Set(ofType.map((t) => t.investigation))].join(", "),
  }
})

// Solid materials, the ones the habitat check asks about
const config = {
  burned: { label: "Kept burning", color: "var(--chart-2)" },
  out: { label: "Went out", color: "var(--chart-1)" },
} satisfies ChartConfig
const solids = flightTests.filter((t) => t.fuel_type === "solid")
const rows = Object.entries(MATERIALS)
  .map(([id, m]) => {
    const flown = solids.filter((t) => t.material_family === id)
    return {
      id,
      label: m.label,
      material: `${m.label} (${flown.length})`,
      burned: flown.filter((t) => t.sustained).length,
      out: flown.filter((t) => !t.sustained).length,
      total: flown.length,
    }
  })
  .sort((a, b) => b.total - a.total)

const THIN = 12
const thin = rows.filter((r) => r.total < THIN).map((r) => r.label)
const idOf = (material: string) =>
  rows.find((r) => r.material === material)?.id ?? ""

// Material names on the axis are links to that material's flight tests
function MaterialTick({
  x,
  y,
  payload,
}: {
  x?: number | string
  y?: number | string
  payload?: { value: string }
}) {
  const id = idOf(payload?.value ?? "")
  return (
    <Link href={`/tests?material=${encodeURIComponent(id)}`}>
      <text
        x={x}
        y={y}
        dy={4}
        textAnchor="end"
        className="fill-foreground text-xs underline-offset-2 hover:underline"
      >
        {payload?.value}
      </text>
    </Link>
  )
}

function ShareBar({ kept, tests }: { kept: number; tests: number }) {
  const share = tests ? kept / tests : 0
  return (
    <div className="flex items-center gap-2">
      <div className="flex h-2 w-24 overflow-hidden rounded-full bg-chart-1">
        <div className="bg-chart-2" style={{ width: `${share * 100}%` }} />
      </div>
      <span className="tabular-nums">{Math.round(share * 100)} %</span>
    </div>
  )
}

export default function CoveragePage() {
  const router = useRouter()
  const openTests = (id: string) =>
    router.push(`/tests?material=${encodeURIComponent(id)}`)
  const [burnerLow, burnerHigh] = model.pressure_source.pressure_range_atm

  return (
    <>
      <PageHeader title="Coverage" />
      <div className="flex flex-col gap-4 p-4 md:p-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1">
              What the model learned from
              <InfoHint>
                Flight tests with a flame outcome, an oxygen level and a
                pressure. Smoke tests and inverse flames are left out.
              </InfoHint>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Tests</TableHead>
                  <TableHead>Kept burning</TableHead>
                  <TableHead>O2, %</TableHead>
                  <TableHead>Pressure, atm</TableHead>
                  <TableHead>Investigations</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {byType.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>
                      <Link
                        href={`/tests?type=${encodeURIComponent(r.id)}`}
                        className="font-medium underline-offset-2 hover:underline"
                      >
                        {r.name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.tests}
                    </TableCell>
                    <TableCell>
                      <ShareBar kept={r.kept} tests={r.tests} />
                    </TableCell>
                    <TableCell className="tabular-nums">{r.o2}</TableCell>
                    <TableCell className="tabular-nums">{r.pressure}</TableCell>
                    <TableCell className="max-w-72 truncate text-muted-foreground">
                      {r.investigations}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
          <CardFooter className="flex-wrap justify-end gap-1">
            <Button asChild variant="ghost" size="sm">
              <a
                href={`${REPO}/blob/master/data/processed/tests.csv`}
                target="_blank"
                rel="noreferrer"
              >
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
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Solid materials</CardTitle>
          </CardHeader>
          <CardContent>
            <ChartContainer config={config} className="aspect-auto h-72 w-full">
              <BarChart
                data={rows}
                layout="vertical"
                margin={{ left: 8, right: 40 }}
              >
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
                <ChartLegend
                  verticalAlign="top"
                  content={<ChartLegendContent />}
                />
                <Bar
                  dataKey="burned"
                  stackId="a"
                  fill="var(--color-burned)"
                  radius={[4, 0, 0, 4]}
                  className="cursor-pointer"
                  onClick={(d) => openTests(d.payload.id)}
                />
                <Bar
                  dataKey="out"
                  stackId="a"
                  fill="var(--color-out)"
                  radius={[0, 4, 4, 0]}
                  className="cursor-pointer"
                  onClick={(d) => openTests(d.payload.id)}
                />
              </BarChart>
            </ChartContainer>
          </CardContent>
          <CardFooter>
            <span className="text-xs text-muted-foreground">
              Click a material to see its tests.
            </span>
          </CardFooter>
        </Card>

        <Alert>
          <InfoIcon />
          <AlertTitle>Thin evidence</AlertTitle>
          <AlertDescription>
            {thin.join(", ")} have fewer than {THIN} flight tests each. Every
            solid was flown at {model.solids.pressure_range_atm[0]} to{" "}
            {model.solids.pressure_range_atm[1]} atm: below that, the pressure
            effect comes from{" "}
            {model.pressure_source.investigations.join(" and ")} gas-burner
            tests ({burnerLow} to {burnerHigh} atm).
          </AlertDescription>
        </Alert>
      </div>
    </>
  )
}
