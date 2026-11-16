"use client"

import Link from "next/link"
import { ArrowRightIcon, BookOpenIcon } from "lucide-react"

import { EvidenceBadge } from "@/components/evidence-badge"
import { LeverList } from "@/components/lever-list"
import { NothingFound } from "@/components/nothing-found"
import { PageHeader } from "@/components/page-header"
import { ScenarioBar } from "@/components/scenario-bar"
import { SourceLink } from "@/components/source-link"
import { useScenario } from "@/components/scenario-provider"
import { TestsTable } from "@/components/tests-table"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { MethodPopover, RangeBar } from "@/components/verdict-detail"
import { burnProbability, likelyRange, safetyLevers } from "@/lib/model"
import {
  closestTests,
  evidenceFor,
  findingsAbout,
  flownTests,
} from "@/lib/evidence"
import {
  HABITATS,
  MATERIALS,
  pct,
  verdictOf,
  type Verdict,
} from "@/lib/scenario"

const SENTENCE: Record<Verdict, string> = {
  burns: "keeps burning",
  borderline: "may keep burning",
  "self-extinguishes": "goes out on its own",
}

function MoreLink({
  href,
  children,
}: {
  href: string
  children: React.ReactNode
}) {
  return (
    <Button asChild variant="ghost" size="sm">
      <Link href={href}>
        {children}
        <ArrowRightIcon data-icon="inline-end" />
      </Link>
    </Button>
  )
}

export default function HabitatCheckPage() {
  const { scenario, habitatId } = useScenario()
  const probability = burnProbability(scenario)
  const verdict = verdictOf(probability)
  const levers = safetyLevers(scenario)
  const evidence = evidenceFor(scenario)
  const reports = findingsAbout(scenario.material)
  const flown = flownTests(scenario.material)
  const [low, high] = likelyRange(scenario)
  const material = MATERIALS[scenario.material].label
  const habitat =
    HABITATS.find((h) => h.id === habitatId)?.phrase ?? "in this atmosphere"

  return (
    <>
      <PageHeader title="Habitat check" />
      <ScenarioBar />
      <div className="flex flex-col gap-4 p-4 md:p-8">
        {/* Two independent columns: each card is as tall as its content */}
        <div className="grid items-start gap-4 lg:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">
                  {material} {SENTENCE[verdict]} {habitat}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div>
                  <p className="text-4xl font-semibold tabular-nums">
                    {pct(probability)} %
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {/* Outside the flight data the refits all extrapolate alike: a tight range would mislead */}
                    {evidence.level === "extrapolated"
                      ? "chance a flame keeps spreading, indicative only: outside the flight data"
                      : `chance a flame keeps spreading, likely ${pct(low)} to ${pct(high)} %`}
                  </p>
                </div>
                <RangeBar
                  value={probability}
                  low={evidence.level === "extrapolated" ? probability : low}
                  high={evidence.level === "extrapolated" ? probability : high}
                />
                <div className="flex items-center gap-2 text-sm">
                  <EvidenceBadge level={evidence.level} />
                  <span className="text-muted-foreground">
                    {evidence.reason}
                  </span>
                </div>
              </CardContent>
              <CardFooter className="justify-between">
                <MethodPopover />
                {flown.length > 0 && (
                  <MoreLink href="/map">See the tests on the map</MoreLink>
                )}
              </CardFooter>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Closest tests in orbit</CardTitle>
                <CardDescription>
                  Same material, nearest oxygen and flow.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <TestsTable
                  tests={closestTests(scenario, 5)}
                  empty={`No flight test of ${material} yet.`}
                  compact
                />
              </CardContent>
              {flown.length > 5 && (
                <CardFooter>
                  <MoreLink href="/tests">All tests</MoreLink>
                </CardFooter>
              )}
            </Card>
          </div>
          <div className="flex min-w-0 flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>What would stop it</CardTitle>
              </CardHeader>
              <CardContent>
                <LeverList levers={levers} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>What the reports say about {material}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                {reports.length === 0 && (
                  <NothingFound
                    icon={BookOpenIcon}
                    title={`No report finding on ${material}`}
                    reason="NASA's reports do not discuss this material."
                  />
                )}
                {reports.slice(0, 4).map((f) => (
                  <figure
                    key={`${f.psi_id}-${f.quote}`}
                    className="flex flex-col gap-1"
                  >
                    <span className="text-xs text-muted-foreground">
                      {f.type}
                    </span>
                    <figcaption className="font-medium">{f.value}</figcaption>
                    <blockquote className="line-clamp-2 text-muted-foreground">
                      “{f.quote}”
                    </blockquote>
                    <SourceLink finding={f} />
                  </figure>
                ))}
              </CardContent>
              {reports.length > 4 && (
                <CardFooter>
                  <MoreLink
                    href={`/findings?material=${encodeURIComponent(scenario.material)}`}
                  >
                    All {reports.length} findings on {material}
                  </MoreLink>
                </CardFooter>
              )}
            </Card>
          </div>
        </div>
      </div>
    </>
  )
}
