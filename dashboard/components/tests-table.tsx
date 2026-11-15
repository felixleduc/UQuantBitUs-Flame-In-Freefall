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
import type { Test } from "@/lib/data"

const value = (v: number | undefined, unit: string) =>
  v === undefined ? "·" : `${Math.round(v * 10) / 10} ${unit}`

export function TestsTable({
  tests,
  empty,
  compact = false,
}: {
  tests: Test[]
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
          {!compact && <TableHead>Material</TableHead>}
          <TableHead>Sample</TableHead>
          <TableHead className="text-right">O2</TableHead>
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
              <TableCell className="max-w-48 truncate">{t.material}</TableCell>
            )}
            <TableCell className="text-muted-foreground">
              {t.geometry ?? "·"}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {value(t.o2_percent, "%")}
            </TableCell>
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
