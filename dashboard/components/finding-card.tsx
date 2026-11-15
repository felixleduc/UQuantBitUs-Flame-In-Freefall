import { SourceLink } from "@/components/source-link"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { Finding } from "@/lib/data"

export function FindingCard({ finding }: { finding: Finding }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription className="text-xs">{finding.type}</CardDescription>
        <CardTitle className="text-sm">{finding.value}</CardTitle>
      </CardHeader>
      <CardContent>
        <blockquote className="text-sm text-muted-foreground">
          “{finding.quote}”
        </blockquote>
      </CardContent>
      <CardFooter>
        <SourceLink finding={finding} />
      </CardFooter>
    </Card>
  )
}
