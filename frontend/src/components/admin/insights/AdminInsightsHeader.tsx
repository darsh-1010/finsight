import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { RefreshCw } from "lucide-react";

const AdminInsightsHeader = ({
  refetch,
  isFetching,
}: {
  refetch: () => void;
  isFetching: boolean;
}) => (
  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
    <div>
      <h1 className="text-2xl font-bold tracking-tight">
        Insights Review
      </h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Review synced market insights and control what becomes visible to users.
      </p>
    </div>
    <div className="flex gap-3 flex-col sm:flex-row sm:items-center">
      <div className="rounded-full border border-border bg-card px-4 py-2 flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
        <span className="text-xs text-muted-foreground">Approval Queue:</span>
        <span className="text-xs font-semibold">Admin only</span>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => refetch()}
        disabled={isFetching}
        className="rounded-full px-4 h-9"
      >
        <RefreshCw className={cn("mr-2 h-3.5 w-3.5", isFetching && "animate-spin")} />
        Refresh
      </Button>
    </div>
  </div>
);

export default AdminInsightsHeader;
