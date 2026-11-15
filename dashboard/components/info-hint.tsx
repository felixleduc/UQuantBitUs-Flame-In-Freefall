import { InfoIcon } from "lucide-react"

import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"

// A small "i" next to a title; the note opens on hover or focus, in the same light
// card as the other hover details of the dashboard.
export function InfoHint({ children }: { children: React.ReactNode }) {
  return (
    <HoverCard openDelay={100} closeDelay={100}>
      <HoverCardTrigger asChild>
        <button
          type="button"
          aria-label="More information"
          className="inline-flex size-6 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
        >
          <InfoIcon className="size-4" />
        </button>
      </HoverCardTrigger>
      <HoverCardContent className="w-64 text-sm">{children}</HoverCardContent>
    </HoverCard>
  )
}
