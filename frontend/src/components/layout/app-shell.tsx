"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BoundingBox, Camera, ChartBar, Cube, Database, ImageSquare } from "@phosphor-icons/react";

import { cn } from "@/lib/utils";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
} from "@/components/ui/sidebar";

const navigation = [
  { href: "/dashboard", label: "儀表板", icon: ChartBar },
  { href: "/detection", label: "影像辨識", icon: ImageSquare },
  { href: "/live-detection", label: "即時辨識", icon: Camera },
  { href: "/batches", label: "批次紀錄", icon: Database },
  { href: "/models", label: "模型", icon: Cube },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <SidebarProvider
      style={
        {
          "--sidebar-width": "16rem",
          "--sidebar-width-icon": "4rem",
        } as React.CSSProperties
      }
    >
      <Sidebar collapsible="icon" className="border-r bg-background">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" className="pointer-events-none mb-2 mt-2">
                <div className="flex aspect-square size-8 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <BoundingBox size={20} weight="duotone" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                  <span className="truncate font-semibold tracking-tight text-foreground">BarcodeCV</span>
                  <span className="truncate text-xs text-muted-foreground">營運主控台</span>
                </div>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel className="group-data-[collapsible=icon]:opacity-0 font-medium">導覽</SidebarGroupLabel>
            <SidebarMenu>
              {navigation.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || pathname.startsWith(`${href}/`);
                return (
                  <SidebarMenuItem key={href}>
                    <SidebarMenuButton asChild isActive={active} tooltip={label} className="transition-colors duration-150">
                      <Link href={href} className="flex w-full items-center gap-3">
                        <Icon size={18} weight={active ? "fill" : "regular"} className={cn(active ? "text-primary" : "text-muted-foreground")} />
                        <span className="truncate font-medium">{label}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>

      <SidebarRail />

      <SidebarInset className="bg-muted/30">
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-14 lg:px-6">
          <div className="flex flex-1 items-center gap-3">
            <SidebarTrigger className="-ml-1" />
            <div className="h-4 w-px bg-border" />
            <p className="text-xs text-muted-foreground">正式環境營運工作區</p>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-4 md:p-6 lg:p-8">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
