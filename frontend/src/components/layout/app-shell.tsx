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
        <SidebarHeader className="border-b border-[#334155]/50 bg-[#0b0c10]">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" className="pointer-events-none mb-2 mt-2">
                <div className="flex aspect-square size-10 items-center justify-center rounded-[0.25rem] bg-[#1a202c] text-[#00f0ff] border border-[#00f0ff]/30 shadow-[0_0_12px_#00f0ff30]">
                  <BoundingBox size={24} weight="duotone" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden ml-1">
                  <span className="truncate font-black tracking-wider text-white text-lg drop-shadow-[0_0_2px_#00f0ff]">BarcodeCV</span>
                  <span className="truncate text-[10px] font-mono text-[#00f0ff]/80 font-bold uppercase tracking-widest">VISION SYNC</span>
                </div>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel className="group-data-[collapsible=icon]:opacity-0 font-mono text-xs uppercase tracking-widest text-[#00f0ff]/70">系統導航</SidebarGroupLabel>
            <SidebarMenu>
              {navigation.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || pathname.startsWith(`${href}/`);
                return (
                  <SidebarMenuItem key={href}>
                    <SidebarMenuButton 
                      asChild 
                      isActive={active} 
                      tooltip={label} 
                      className={cn(
                        "transition-all duration-200 hover:bg-[#1a202c] hover:text-[#00f0ff]",
                        active && "bg-[#1a202c] text-[#00f0ff] relative before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:h-2/3 before:w-1 before:bg-[#00f0ff] before:rounded-r-md before:shadow-[0_0_8px_#00f0ff]"
                      )}
                    >
                      <Link href={href} className="flex w-full items-center gap-3">
                        <Icon size={20} weight={active ? "duotone" : "regular"} className={cn(active ? "text-[#00f0ff]" : "text-muted-foreground")} />
                        <span className="truncate font-medium tracking-wide">{label}</span>
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

      <SidebarInset className="bg-[#050508] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[#161b22]/30 via-[#050508] to-[#050508]">
        <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b border-[#334155]/50 bg-[#0b0c10]/80 backdrop-blur-md px-4 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-14 lg:px-6 shadow-sm shadow-[#00f0ff]/5">
          <div className="flex flex-1 items-center gap-3">
            <SidebarTrigger className="-ml-1 text-muted-foreground hover:text-[#00f0ff] transition-colors" />
            <div className="h-4 w-[1px] bg-[#334155]" />
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00ff66] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00ff66]"></span>
              </span>
              <p className="text-xs font-mono text-muted-foreground tracking-wider uppercase">SYSTEM ONLINE : CORE READY</p>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 p-4 md:p-6 lg:p-8 animate-in fade-in duration-500">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
