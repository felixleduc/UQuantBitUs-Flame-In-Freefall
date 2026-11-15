import {
  CircleAlertIcon,
  CircleCheckIcon,
  TriangleAlertIcon,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { Evidence } from "@/lib/evidence"
import { cn } from "@/lib/utils"

// Status color on the icon only, always with its label.
const STYLE = {
  strong: {
    icon: CircleCheckIcon,
    color: "text-good",
    label: "Strong evidence",
  },
  limited: {
    icon: CircleAlertIcon,
    color: "text-warning",
    label: "Limited evidence",
  },
  extrapolated: {
    icon: TriangleAlertIcon,
    color: "text-critical",
    label: "Extrapolated",
  },
} satisfies Record<
  Evidence["level"],
  { icon: typeof CircleCheckIcon; color: string; label: string }
>

export function EvidenceBadge({ level }: { level: Evidence["level"] }) {
  const { icon: Icon, color, label } = STYLE[level]
  return (
    <Badge variant="outline">
      <Icon data-icon="inline-start" className={cn(color)} />
      {label}
    </Badge>
  )
}
