import { CircleCheckIcon, FlameIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"

// Status color is carried by the icon only, always next to its label.
export function OutcomeBadge({
  sustained,
  outcome,
}: {
  sustained?: boolean | null
  outcome?: string
}) {
  if (sustained == null)
    return <Badge variant="secondary">{outcome ?? "unknown"}</Badge>
  return (
    <Badge variant="outline">
      {sustained ? (
        <FlameIcon data-icon="inline-start" className="text-critical" />
      ) : (
        <CircleCheckIcon data-icon="inline-start" className="text-good" />
      )}
      {outcome}
    </Badge>
  )
}
