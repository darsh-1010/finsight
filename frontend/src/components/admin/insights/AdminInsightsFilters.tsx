import React from "react";
import { cn } from "@/lib/utils";

const getStatusColor = (status: string) => {
  switch (status.toLowerCase()) {
    case 'draft': return 'bg-gray-400';
    case 'published': return 'bg-green-500';
    case 'approved': return 'bg-blue-500';
    case 'rejected': return 'bg-red-500';
    case 'pending': return 'bg-yellow-500';
    case 'archived': return 'bg-zinc-500';
    default: return 'bg-gray-400';
  }
};

const STATUSES = ['draft', 'approved', 'rejected', 'archived'];

export type TrendType = 'all' | 'daily' | 'weekly';

interface AdminInsightsFiltersProps {
  activeStatus: string;
  setActiveStatus: (status: string) => void;
  trendFilter: TrendType;
  setTrendFilter: (trend: TrendType) => void;
  tierFilteredInsights: { status: string }[];
  activeTier: number | null;
}

const AdminInsightsFilters: React.FC<AdminInsightsFiltersProps> = ({
  activeStatus,
  setActiveStatus,
  trendFilter,
  setTrendFilter,
  tierFilteredInsights,
  activeTier,
}) => {
  const isTier1Or2 = activeTier === 1 || activeTier === 2;
  const trendOptions = (['all', 'daily', 'weekly'] as const);

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-xl border border-border bg-card p-2 shadow-sm">
      <div className="flex items-center gap-1 overflow-x-auto w-full">
        <button 
          onClick={() => setActiveStatus('all')}
          className={cn(
            "flex h-8 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-all shrink-0",
            activeStatus === 'all' ? "bg-primary/50 text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-secondary/80 hover:text-foreground"
          )}
        >
          All <span className={cn("ml-1 rounded-full px-1.5 py-0.5 text-[10px]", activeStatus === 'all' ? "bg-primary-foreground/20" : "bg-secondary")}>{tierFilteredInsights.length}</span>
        </button>
        
        {STATUSES.map(s => {
          const count = tierFilteredInsights.filter(i => i.status.toLowerCase() === s).length;
          return (
            <button 
              key={s}
              onClick={() => setActiveStatus(s)}
              className={cn(
                "flex h-8 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-all capitalize shrink-0",
                activeStatus === s ? "bg-primary/50 text-primary-foreground shadow-sm" : "text-muted-foreground hover:bg-secondary/80 hover:text-foreground"
              )}
            >
              <span className={cn("h-2 w-2 rounded-full ring-2 ring-transparent transition-all", getStatusColor(s), activeStatus === s ? "ring-primary-foreground/30" : "")} />
              {s} <span className={cn("ml-1 rounded-full px-1.5 py-0.5 text-[10px]", activeStatus === s ? "bg-primary-foreground/20" : "bg-secondary")}>{count}</span>
            </button>
          )
        })}
      </div>
      
      {!isTier1Or2 && (
        <div className="flex items-center rounded-lg bg-secondary/50 p-1 shrink-0 w-full sm:w-auto">
          {trendOptions.map((trend) => (
            <button
              key={trend}
              onClick={() => setTrendFilter(trend)}
              className={cn(
                "flex-1 sm:flex-none capitalize px-4 py-1.5 text-xs font-medium rounded-md transition-all",
                trendFilter === trend 
                  ? "bg-background text-foreground shadow-sm" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {trend}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default AdminInsightsFilters;
