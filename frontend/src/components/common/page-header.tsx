import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

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
    <div className="mb-6 flex flex-col gap-4 rounded-xl border border-border/50 bg-background/40 p-6 shadow-sm backdrop-blur-md md:flex-row md:items-start md:justify-between">
      <div className="space-y-3">
        {badge ? <Badge variant="secondary" className="bg-secondary/50 hover:bg-secondary border-none shadow-none">{badge}</Badge> : null}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">{action}</div>
    </div>
  );
}
