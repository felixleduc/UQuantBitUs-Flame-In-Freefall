"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BookOpenIcon,
  ChartScatterIcon,
  DatabaseIcon,
  FlaskConicalIcon,
  ShieldCheckIcon,
} from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

const NAV = [
  {
    label: "Assess",
    items: [
      { href: "/", title: "Habitat check", icon: ShieldCheckIcon },
      { href: "/map", title: "Flammability heat map", icon: ChartScatterIcon },
    ],
  },
  {
    label: "Evidence",
    items: [
      { href: "/tests", title: "Space tests", icon: FlaskConicalIcon },
      { href: "/findings", title: "Findings", icon: BookOpenIcon },
    ],
  },
  {
    label: "Data",
    items: [{ href: "/coverage", title: "Coverage", icon: DatabaseIcon }],
  },
]

export function AppSidebar() {
  const pathname = usePathname()

  return (
    <Sidebar collapsible="icon">
      <SidebarContent>
        {NAV.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton
                      asChild
                      isActive={pathname === item.href}
                      tooltip={item.title}
                    >
                      <Link href={item.href}>
                        <item.icon />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
    </Sidebar>
  )
}
