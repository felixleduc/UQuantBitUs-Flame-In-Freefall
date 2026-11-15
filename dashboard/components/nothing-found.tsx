import type { LucideIcon } from "lucide-react"

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"

// One empty state for every card: an icon, what is missing, and why.
export function NothingFound({
  icon: Icon,
  title,
  reason,
}: {
  icon: LucideIcon
  title: string
  reason?: string
}) {
  return (
    <Empty className="py-6">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyTitle className="text-sm">{title}</EmptyTitle>
        {reason && <EmptyDescription>{reason}</EmptyDescription>}
      </EmptyHeader>
    </Empty>
  )
}
