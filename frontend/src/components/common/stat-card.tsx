import { ArrowUpRight } from "@phosphor-icons/react/dist/ssr";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <Card className="relative overflow-hidden rounded-xl border-border/50 bg-background/50 shadow-sm backdrop-blur-xl transition-all hover:bg-background/60 hover:shadow-md">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-3xl font-semibold tracking-tight">{value}</p>
            <p className="mt-2 text-xs text-muted-foreground">{hint}</p>
          </div>
          <div className="rounded-full bg-primary/10 p-2 text-primary">
            <ArrowUpRight size={16} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
