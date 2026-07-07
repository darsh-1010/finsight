import { AlertCircle, CircleDashed, RefreshCw } from 'lucide-react';

const LoadingState = () => (
  <div className="flex items-center justify-center gap-2 rounded-lg border border-border bg-card p-12 text-muted-foreground">
    <RefreshCw className="h-5 w-5 animate-spin" />
    Loading insights
  </div>
);

const ErrorState = () => (
  <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-5 text-red-700 dark:border-red-900/30 dark:bg-red-950/20 dark:text-red-300">
    <AlertCircle className="h-5 w-5" />
    Could not load insights.
  </div>
);

const EmptyState = () => (
  <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-card p-12 text-center">
    <CircleDashed className="mb-3 h-10 w-10 text-muted-foreground" />
    <h2 className="text-lg font-bold">No insights found</h2>
    <p className="mt-1 text-sm text-muted-foreground">
      Synced market insights will appear here for review.
    </p>
  </div>
);

export { EmptyState, ErrorState, LoadingState };
