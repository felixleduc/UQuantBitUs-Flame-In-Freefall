import { FlaskConicalIcon } from "lucide-react"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { NothingFound } from "@/components/nothing-found"
import { OutcomeBadge } from "@/components/verdict-badge"
import { FUEL_TYPES } from "@/lib/fuel-types"

// What both the solid tests (habitat check) and the model's tests (Space tests) provide
export type TestRow = {
  psi_id: string
  investigation: string
  test_id: string
  fuel_type?: string
  material?: string
  material_family?: string
  geometry?: string
  o2_percent?: number
  pressure_atm?: number
  flow_cm_s?: number
  sustained?: boolean | null
  outcome?: string
}

const value = (v: number | undefined, unit: string, digits = 1) =>
  v === undefined
    ? "·"
    : `${Math.round(v * 10 ** digits) / 10 ** digits} ${unit}`

export function TestsTable({
  tests,
  empty,
  compact = false,
}: {
  tests: TestRow[]
  empty: string
  compact?: boolean
}) {
  if (tests.length === 0)
    return <NothingFound icon={FlaskConicalIcon} title={empty} />
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Test</TableHead>
          {!compact && <TableHead>Type</TableHead>}
          {!compact && <TableHead>Fuel or material</TableHead>}
          <TableHead>Sample</TableHead>
          <TableHead className="text-right">O2</TableHead>
          {!compact && <TableHead className="text-right">Pressure</TableHead>}
          <TableHead className="text-right">Flow</TableHead>
          <TableHead>Outcome</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {tests.map((t) => (
          <TableRow key={`${t.psi_id}-${t.test_id}`}>
            <TableCell>
              <span className="font-medium">{t.investigation}</span>{" "}
              <span className="text-muted-foreground">{t.test_id}</span>
            </TableCell>
            {!compact && (
              <TableCell className="text-muted-foreground">
                {FUEL_TYPES[t.fuel_type ?? ""] ?? t.fuel_type ?? "·"}
              </TableCell>
            )}
            {!compact && (
              <TableCell className="max-w-48 truncate">
                {t.material ?? t.material_family ?? "·"}
              </TableCell>
            )}
            <TableCell className="text-muted-foreground">
              {t.geometry ?? "·"}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {value(t.o2_percent, "%")}
            </TableCell>
            {!compact && (
              <TableCell className="text-right tabular-nums">
                {value(t.pressure_atm, "atm", 2)}
              </TableCell>
            )}
            <TableCell className="text-right tabular-nums">
              {value(t.flow_cm_s, "cm/s")}
            </TableCell>
            <TableCell>
              <OutcomeBadge sustained={t.sustained} outcome={t.outcome} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
