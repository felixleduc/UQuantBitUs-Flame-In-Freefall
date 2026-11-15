"use client"

import { ChevronDownIcon, SlidersHorizontalIcon } from "lucide-react"

import { useScenario } from "@/components/scenario-provider"
import { Button } from "@/components/ui/button"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Popover,
  PopoverContent,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { HABITATS, MATERIALS } from "@/lib/scenario"

const SLIDERS = [
  { key: "o2Percent", label: "Oxygen", unit: "%", min: 12, max: 40, step: 0.5 },
  {
    key: "pressureAtm",
    label: "Pressure",
    unit: "atm",
    min: 0.3,
    max: 1.2,
    step: 0.01,
  },
  {
    key: "flowCmS",
    label: "Ventilation",
    unit: "cm/s",
    min: 0,
    max: 50,
    step: 1,
  },
] as const

// One row above the content: the question is always visible, the fine tuning one click away.
export function ScenarioBar() {
  const { scenario, habitatId, setMaterial, setHabitat, setValue } =
    useScenario()

  return (
    <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3 md:px-8">
      <Select value={scenario.material} onValueChange={setMaterial}>
        <SelectTrigger size="sm" className="w-56" aria-label="Material">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {Object.entries(MATERIALS).map(([id, m]) => (
              <SelectItem key={id} value={id}>
                {m.label}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
      <span className="text-sm text-muted-foreground">in</span>
      <Select
        value={habitatId === "custom" ? "" : habitatId}
        onValueChange={setHabitat}
      >
        <SelectTrigger size="sm" className="w-56" aria-label="Atmosphere">
          <SelectValue placeholder="Custom atmosphere">
            {HABITATS.find((h) => h.id === habitatId)?.label}
          </SelectValue>
        </SelectTrigger>
        <SelectContent position="popper" align="start" className="w-80">
          <SelectGroup>
            {HABITATS.map((h) => (
              <SelectItem key={h.id} value={h.id} textValue={h.label}>
                <span className="flex flex-col whitespace-normal">
                  <span>{h.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {h.detail}. {h.use}
                  </span>
                </span>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
      <Popover>
        <PopoverTrigger asChild>
          {/* Outlined like the other controls, with a verb and a chevron: it reads as a button */}
          <Button variant="outline" size="sm">
            <SlidersHorizontalIcon data-icon="inline-start" />
            Adjust atmosphere
            <span className="text-muted-foreground tabular-nums">
              {scenario.o2Percent} % O2 · {scenario.pressureAtm} atm ·{" "}
              {scenario.flowCmS} cm/s
            </span>
            <ChevronDownIcon data-icon="inline-end" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-80 pb-6">
          <PopoverHeader>
            <PopoverTitle>Atmosphere</PopoverTitle>
          </PopoverHeader>
          <FieldGroup className="mt-1">
            {SLIDERS.map((s) => (
              <Field key={s.key}>
                <div className="flex items-center justify-between">
                  <FieldLabel htmlFor={s.key}>{s.label}</FieldLabel>
                  <span className="text-sm text-muted-foreground tabular-nums">
                    {scenario[s.key]} {s.unit}
                  </span>
                </div>
                <Slider
                  id={s.key}
                  min={s.min}
                  max={s.max}
                  step={s.step}
                  value={[scenario[s.key]]}
                  onValueChange={([v]) => setValue(s.key, v)}
                />
              </Field>
            ))}
          </FieldGroup>
        </PopoverContent>
      </Popover>
    </div>
  )
}
