import { Badge } from "@/components/ui/badge";

export function PageHeader({
  title,
  description,
  badge,
  action,
}: {
  title: string;
  description: string;
  badge?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 rounded-xl border border-[#334155]/60 bg-[#0b0c10]/80 backdrop-blur-md p-6 md:flex-row md:items-start md:justify-between shadow-lg relative overflow-hidden">
      {/* Decorative Grid */}
      <div className="absolute inset-0 bg-[url('/grid-pattern.svg')] bg-[#00f0ff]/5 opacity-20 pointer-events-none mix-blend-screen" />
      <div className="space-y-3 relative z-10">
        {badge ? (
          <Badge variant="outline" className="border-[#00f0ff]/50 text-[#00f0ff] uppercase tracking-widest font-mono text-[10px] bg-[#00f0ff]/5">
            {"// "}{badge}
          </Badge>
        ) : null}
        <div>
          <h1 className="text-3xl font-black tracking-wider text-white drop-shadow-[0_0_2px_#00f0ff]">{title}</h1>
          <p className="mt-2 max-w-3xl text-sm font-mono leading-relaxed text-[#94a3b8] uppercase tracking-wide">{description}</p>
        </div>
      </div>
      <div className="flex shrink-0 items-center justify-end gap-2 relative z-10 w-full md:w-auto">{action}</div>
    </div>
  );
}
