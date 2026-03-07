"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BoundingBox, Camera, ChartBar, Cube, Database, ImageSquare, Scan } from "@phosphor-icons/react";

import { cn } from "@/lib/utils";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
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
  { href: "/models", label: "模型管理", icon: Cube },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <SidebarProvider
      style={{
        "--sidebar-width": "16rem",
        "--sidebar-width-icon": "4rem",
      } as React.CSSProperties}
    >
      {/* Background Layer */}
      <div className="fixed inset-0 z-[-1] min-h-screen w-full bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.10),transparent_28%),linear-gradient(to_bottom,#f8fafc,#eef2ff)] dark:bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.15),transparent_22%),linear-gradient(to_bottom,#09090b,#111827)]" />

      <Sidebar collapsible="icon" className="border-r bg-background/40 backdrop-blur-xl">
            <SidebarHeader>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton size="lg" className="pointer-events-none mb-2 mt-2">
                    <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <BoundingBox size={22} weight="duotone" />
                    </div>
                    <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                      <span className="truncate font-semibold tracking-tight text-foreground">BarcodeCV</span>
                      <span className="truncate text-[10px] tracking-wide text-muted-foreground">視覺辨識控制台</span>
                    </div>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarHeader>

            <SidebarContent>
              <SidebarGroup>
                <SidebarGroupLabel className="group-data-[collapsible=icon]:opacity-0 font-medium">導覽選單</SidebarGroupLabel>
                <SidebarMenu>
                  {navigation.map(({ href, label, icon: Icon }) => {
                    const active = pathname === href || pathname.startsWith(`${href}/`);
                    return (
                      <SidebarMenuItem key={href}>
                        <SidebarMenuButton 
                          asChild 
                          isActive={active} 
                          tooltip={label}
                          className="transition-all duration-200"
                        >
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

            <SidebarFooter>
              
            </SidebarFooter>
          </Sidebar>

          <SidebarRail />

          <SidebarInset className="bg-transparent">
            {/* Top Header Navigation */}
            <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/50 px-4 backdrop-blur-xl transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-14 lg:px-6">
              <div className="flex flex-1 items-center gap-3">
                <SidebarTrigger className="-ml-1" />
                <div className="h-4 w-px bg-border" />
                <div className="flex items-center gap-2">
                  <div className="rounded-full border border-primary/20 bg-primary/5 px-2.5 py-0.5 text-[10px] font-medium tracking-wide text-primary shadow-sm">
                    MVP 測試版
                  </div>
                </div>
              </div>
            </header>
            
            <main className="flex-1 p-4 md:p-6 lg:p-8 w-full max-w-7xl mx-auto space-y-6">
              {children}
            </main>
          </SidebarInset>
    </SidebarProvider>
  );
}
