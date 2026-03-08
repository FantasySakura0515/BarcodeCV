import { Info } from "@phosphor-icons/react/dist/ssr";

import { Card, CardContent } from "@/components/ui/card";

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <Card className="border-dashed bg-card">
      <CardContent className="flex flex-col items-center justify-center gap-3 py-14 text-center">
        <div className="rounded-full bg-muted p-3 text-muted-foreground">
          <Info size={20} />
        </div>
        <div>
          <p className="font-medium">{title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
      </CardContent>
    </Card>
  );
}
