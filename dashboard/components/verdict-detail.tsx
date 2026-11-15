"use client"

import { InfoIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"

// The prediction on a 0 to 100 % track: the likely range as a band, the value as a tick,
// and the verdict zones (under 30 %, 30 to 70 %, over 70 %) as context.
export function RangeBar({
  value,
  low,
  high,
}: {
  value: number
  low: number
  high: number
}) {
  return (
    <div className="flex flex-col gap-1">
      <div
        className="relative h-2 rounded-full bg-muted"
        role="img"
        aria-label={`Likely between ${Math.round(low * 100)} and ${Math.round(high * 100)} %`}
      >
        <div
          className="absolute inset-y-0 rounded-full bg-chart-1/30"
          style={{ left: `${low * 100}%`, width: `${(high - low) * 100}%` }}
        />
        <div
          className="absolute -inset-y-1 w-0.5 rounded-full bg-foreground"
          style={{ left: `${value * 100}%` }}
        />
        {[30, 70].map((t) => (
          <div
            key={t}
            className="absolute inset-y-0 w-px bg-background"
            style={{ left: `${t}%` }}
          />
        ))}
      </div>
      <div className="relative h-4 text-xs whitespace-nowrap text-muted-foreground">
        <span className="absolute left-[15%] -translate-x-1/2">Goes out</span>
        <span className="absolute left-1/2 -translate-x-1/2">Borderline</span>
        <span className="absolute left-[85%] -translate-x-1/2">
          Keeps burning
        </span>
      </div>
    </div>
  )
}

export function MethodPopover() {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm">
          <InfoIcon data-icon="inline-start" />
          How is this computed?
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80">
        <PopoverHeader>
          <PopoverTitle>Method</PopoverTitle>
          <PopoverDescription>
            For now a demo model: a curve per material on oxygen, pressure and
            ventilation. The trained model on NASA flight tests will replace it.
          </PopoverDescription>
        </PopoverHeader>
        <ul className="mt-3 flex flex-col gap-1 text-sm text-muted-foreground">
          <li>70 % or more: keeps burning.</li>
          <li>30 to 70 %: borderline.</li>
          <li>Under 30 %: goes out on its own.</li>
          <li>
            The likely range widens when fewer flight tests are close to the
            scenario.
          </li>
        </ul>
      </PopoverContent>
    </Popover>
  )
}
