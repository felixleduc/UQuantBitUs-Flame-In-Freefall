import { ExternalLinkIcon } from "lucide-react"

import type { Finding } from "@/lib/data"

// "PSI-25_Reports_BASS-II Summary Report.pdf" -> "BASS-II Summary Report.pdf"
const fileName = (path: string) =>
  path
    .split("/")
    .pop()!
    .replace(/^PSI-\d+_[^_]+_/, "")

// Where a finding comes from: the file and page, linked to the PSI page that holds the file
// (the PSI repository has no direct link to a single file).
export function SourceLink({ finding }: { finding: Finding }) {
  return (
    <a
      href={finding.url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex min-w-0 items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:underline"
      title={`Open ${finding.acronym} on NASA PSI, where ${fileName(finding.file)} can be downloaded`}
    >
      <span className="truncate">
        {/* the investigation is named once: in the file name when it is there */}
        {fileName(finding.file).includes(finding.acronym)
          ? fileName(finding.file)
          : `${finding.acronym}, ${fileName(finding.file)}`}
        {finding.page && `, page ${finding.page}`}
      </span>
      <ExternalLinkIcon className="size-3 shrink-0" />
    </a>
  )
}
