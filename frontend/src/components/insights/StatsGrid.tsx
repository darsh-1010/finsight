import React from "react";
import { TrendingUp, TrendingDown, Layers } from "lucide-react";

interface StatsGridProps {
  bullishCount: number;
  bearishCount: number;
  totalCount: number;
  activeTab: "daily" | "weekly";
}

export const StatsGrid: React.FC<StatsGridProps> = ({
  bullishCount,
  bearishCount,
  totalCount,
  activeTab,
}) => {
  return (
    <div className="grid grid-cols-3 divide-x divide-border border border-border bg-card/60 backdrop-blur-sm rounded-2xl overflow-hidden shadow-md">
      <div className="flex flex-col sm:flex-row items-center justify-center gap-2 p-3 text-center sm:text-left hover:bg-secondary/10 transition-colors">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-500/10 text-rose-500">
          <TrendingUp className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[10px] md:text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Bullish
          </p>
          <p className="text-sm md:text-base font-extrabold text-rose-500 leading-none mt-0.5">
            {bullishCount}
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-center gap-2 p-3 text-center sm:text-left hover:bg-secondary/10 transition-colors">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/10 text-red-500">
          <TrendingDown className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[10px] md:text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Bearish
          </p>
          <p className="text-sm md:text-base font-extrabold text-red-500 leading-none mt-0.5">
            {bearishCount}
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-center gap-2 p-3 text-center sm:text-left hover:bg-secondary/10 transition-colors">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#5546FF]/10 text-[#5546FF]">
          <Layers className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[10px] md:text-xs font-semibold text-muted-foreground uppercase tracking-wider truncate max-w-[80px] sm:max-w-none">
            {activeTab === "daily" ? "Today" : "This Week"}
          </p>
          <p className="text-sm md:text-base font-extrabold text-[#5546FF] leading-none mt-0.5">
            {totalCount}
          </p>
        </div>
      </div>
    </div>
  );
};
