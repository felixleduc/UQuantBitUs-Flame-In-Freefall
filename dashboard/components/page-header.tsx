import { SidebarTrigger } from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"

// `demo` marks pages whose numbers come from the demo model rather than flight data.
export function PageHeader({
  title,
  demo = true,
}: {
  title: string
  demo?: boolean
}) {
  return (
    <header className="flex flex-col gap-1 px-4 pt-4 md:px-8 md:pt-8">
      <div className="flex items-center gap-2">
        <SidebarTrigger className="-ml-1 md:hidden" />
        <Separator orientation="vertical" className="h-4 md:hidden" />
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {demo && (
          <Badge variant="secondary" className="ml-auto">
            Demo model
          </Badge>
        )}
      </div>
    </header>
  )
}
