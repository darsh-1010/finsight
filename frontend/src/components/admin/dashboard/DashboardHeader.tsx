import { RefreshCw, ShieldCheck } from 'lucide-react';
import React from 'react';

import { Button } from '@/components/ui/button';

interface DashboardHeaderProps {
  isFetchingAll: boolean;
  onRefresh: () => void;
}

const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  isFetchingAll,
  onRefresh,
}) => (
  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
    <div>
      <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight bg-linear-to-r from-primary via-blue-500 to-rose-400 bg-clip-text text-transparent">
          Admin Control Center
      </h1>
      <p className="text-muted-foreground mt-2 flex items-center gap-2 text-sm md:text-base">
        <ShieldCheck className="w-4 h-4 text-rose-500" /> Platform scraping pipelines and market insights monitor
      </p>
    </div>

    <div className="flex items-center gap-3">
      <Button
        variant="outline"
        size="sm"
        onClick={onRefresh}
        disabled={isFetchingAll}
        className="gap-2 h-10 px-4 rounded-xl border-border bg-card hover:bg-secondary/5 font-semibold text-xs"
      >
        <RefreshCw className={`w-3.5 h-3.5 ${isFetchingAll ? 'animate-spin' : ''}`} />
          Refresh Data
      </Button>

      <div className="hidden sm:block p-3 bg-secondary/15 backdrop-blur-xs rounded-xl border border-border">
        <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider leading-none">
            Server State
        </p>
        <div className="flex items-center gap-2 mt-1.5">
          <span className="w-2 h-2 bg-rose-500 rounded-full animate-pulse" />
          <span className="text-xs font-semibold">Pipelines Operational</span>
        </div>
      </div>
    </div>
  </div>
);

export default DashboardHeader;
