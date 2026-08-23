/* eslint-disable max-lines-per-function */
import { Sparkles, CheckCircle2, ChevronRight } from 'lucide-react';
import { useRouter } from 'next/navigation';
import React from 'react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { InsightResponse } from '@/store/apiSlice';

interface PendingApprovalQueueProps {
  pendingInsights: InsightResponse[];
  isInsightsLoading: boolean;
  isUpdating: boolean;
  onQuickApproval: (id: string, status: 'approved' | 'rejected') => Promise<void>;
}

const formatDate = (dateStr?: string | null): string => {
  if (!dateStr) return 'N/A';
  try {
    const date = new Date(dateStr);

    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  } catch {
    return 'Invalid date';
  }
};

const PendingApprovalQueue: React.FC<PendingApprovalQueueProps> = ({
  pendingInsights,
  isInsightsLoading,
  isUpdating,
  onQuickApproval,
}) => {
  const navigate = useRouter().push;

  return (
    <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-xs">
      <div className="p-6 border-b border-border flex items-center justify-between bg-secondary/5">
        <div>
          <h3 className="text-lg font-bold flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-500" /> Pending Approval Queue
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Approve or reject scraped insights immediately to update client feeds.
          </p>
        </div>
        <button
          onClick={() => navigate('/admin/insights')}
          className="text-xs text-primary font-bold hover:underline flex items-center gap-1"
        >
          Go to Insights <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="p-6 space-y-4">
        {isInsightsLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        ) : pendingInsights.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center px-4 bg-rose-500/5 rounded-xl border border-rose-500/10">
            <CheckCircle2 className="w-12 h-12 text-rose-500 mb-3" />
            <h4 className="text-sm font-bold text-rose-600 dark:text-rose-400">Queue is Empty</h4>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
              Outstanding job! All ingested market insights have been reviewed.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {pendingInsights.slice(0, 3).map((insight) => (
              <div
                key={insight.id}
                className="p-4 border border-border rounded-xl bg-card hover:bg-secondary/5 hover:border-primary/25 transition-all duration-200"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="font-black text-sm uppercase bg-secondary px-2.5 py-1 rounded-md border border-border text-foreground">
                      {insight.ticker || 'MARKET'}
                    </span>
                    <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-500 border border-blue-500/20">
                      {insight.trend_type || 'daily'}
                    </span>
                    {insight.source && (
                      <span className="text-[10px] font-medium text-muted-foreground">
                        Source: {insight.source}
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    Created {formatDate(insight.created_at)}
                  </span>
                </div>

                <p className="text-sm mt-3 text-foreground font-medium line-clamp-2 leading-relaxed">
                  {insight.alert_message || insight.summary || 'No summary available.'}
                </p>

                <div className="flex items-center justify-between mt-4 pt-3 border-t border-border/60">
                  <span className="text-xs text-muted-foreground font-semibold">
                    Requires Tier {insight.tier_required}
                  </span>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={isUpdating}
                      onClick={() => onQuickApproval(insight.id, 'rejected')}
                      className="h-8 rounded-lg text-xs font-semibold px-3 py-1 cursor-pointer"
                    >
                      Reject
                    </Button>
                    <Button
                      variant="default"
                      size="sm"
                      disabled={isUpdating}
                      onClick={() => onQuickApproval(insight.id, 'approved')}
                      className="h-8 rounded-lg text-xs font-semibold px-3 py-1 cursor-pointer bg-rose-600 hover:bg-rose-700 text-white"
                    >
                      Approve
                    </Button>
                  </div>
                </div>
              </div>
            ))}

            {pendingInsights.length > 3 && (
              <button
                onClick={() => navigate('/admin/insights')}
                className="w-full text-center py-2 text-xs text-muted-foreground font-semibold hover:text-primary hover:underline border border-dashed border-border rounded-xl mt-2 block"
              >
                View remaining {pendingInsights.length - 3} pending insights
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default PendingApprovalQueue;
