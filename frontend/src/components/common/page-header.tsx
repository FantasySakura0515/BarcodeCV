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
    <div className="mb-6 flex flex-col gap-4 rounded-xl border bg-card p-6 md:flex-row md:items-start md:justify-between">
      <div className="space-y-2">
        {badge ? <Badge variant="secondary">{badge}</Badge> : null}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">{action}</div>
    </div>
  );
}
