import {
  Search,
  Filter,
  ChevronUp,
  ChevronDown,
  ExternalLink,
} from 'lucide-react';
import React from 'react';

import {
  formatPriceChange,
  getFaviconUrl,
  getShortLabel,
  getGroupDateLabel,
} from './helpers';
import type { MarketInsight } from './marketInsightTypes';

import { cn } from '@/lib/utils';


interface ArchiveViewProps {
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  trendFilter: string;
  setTrendFilter: (t: string) => void;
  showFilterPanel: boolean;
  setShowFilterPanel: (show: boolean) => void;
  sortedDateKeys: string[];
  groupedByDate: Record<string, MarketInsight[]>;
  expandedArchiveDateGroups: Record<string, boolean>;
  setExpandedArchiveDateGroups: React.Dispatch<
    React.SetStateAction<Record<string, boolean>>
  >;
  expandedArchiveSignalId: string | null;
  setExpandedArchiveSignalId: (id: string | null) => void;
  highlightedSignalId?: string | null;
}

export const ArchiveView: React.FC<ArchiveViewProps> = ({
  searchQuery,
  setSearchQuery,
  trendFilter,
  setTrendFilter,
  showFilterPanel,
  setShowFilterPanel,
  sortedDateKeys,
  groupedByDate,
  expandedArchiveDateGroups,
  setExpandedArchiveDateGroups,
  expandedArchiveSignalId,
  setExpandedArchiveSignalId,
  highlightedSignalId,
}) => (
  <div className="space-y-3">
    {/* Archive Header Banner */}
    <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-3 text-left text-xs text-indigo-600 dark:text-indigo-400 flex items-start gap-2 leading-relaxed shadow-sm">
      <span className="shrink-0 text-sm">⚠️</span>
      <p>
        <strong>Archive mode:</strong> Showing historical signals. Click date groups to expand, or search to filter by tickers or key events.
      </p>
    </div>

    {/* Search & Filter Row */}
    <div className="flex flex-col sm:flex-row gap-2.5 w-full items-stretch sm:items-center">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search ticker, headline..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-xl border border-border bg-card py-2 pl-9 pr-4 text-xs md:text-sm text-foreground placeholder-muted-foreground focus:outline-none focus:ring-1 focus:ring-[#9C6F0E] focus:border-[#9C6F0E] shadow-sm"
        />
      </div>
      <div className="relative shrink-0">
        <button
          onClick={() => setShowFilterPanel(!showFilterPanel)}
          className={cn(
            'w-full flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-4 py-2 text-xs md:text-sm font-semibold text-foreground hover:bg-secondary/40 transition-all cursor-pointer shadow-sm',
            trendFilter !== 'all' ? 'border-[#9C6F0E] text-[#9C6F0E] bg-[#9C6F0E]/5' : '',
          )}
        >
          <Filter className="h-4 w-4" />
          <span>Filter: <span className="capitalize text-primary">{trendFilter}</span></span>
        </button>

        {showFilterPanel && (
          <div className="absolute right-0 mt-2 w-48 rounded-xl border border-border bg-card p-2 shadow-2xl z-20">
            <div className="text-xs font-bold text-muted-foreground px-3 py-1.5 uppercase tracking-wider">
                Filter Trend
            </div>
            {['all', 'bullish', 'bearish', 'neutral'].map((opt) => (
              <button
                key={opt}
                onClick={() => {
                  setTrendFilter(opt);
                  setShowFilterPanel(false);
                }}
                className={cn(
                  'w-full text-left rounded-lg px-3 py-2 text-xs font-semibold capitalize hover:bg-secondary/40 transition-all cursor-pointer',
                  trendFilter === opt
                    ? 'text-[#9C6F0E] bg-[#9C6F0E]/10 font-bold'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {opt}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>

    {sortedDateKeys.length === 0 ? (
      <div className="text-center p-12 text-muted-foreground text-sm border border-dashed border-border rounded-xl">
          No archived signals found matching your filters.
      </div>
    ) : (
      <div className="space-y-3">
        {sortedDateKeys.map((dateKey) => {
          const label = getGroupDateLabel(dateKey);
          const isGroupExpanded = !!expandedArchiveDateGroups[dateKey];
          const items = groupedByDate[dateKey];

          return (
            <div
              key={dateKey}
              className="rounded-xl border border-border bg-background overflow-hidden"
            >
              <button
                onClick={() => setExpandedArchiveDateGroups((prev) => ({
                  ...prev,
                  [dateKey]: !prev[dateKey],
                }))
                }
                className="w-full flex items-center justify-between bg-card px-4 py-3 text-left border-b border-border/40 hover:bg-secondary/40 transition-all cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm sm:text-base font-bold text-foreground">
                    {label}
                  </span>
                  <span className="rounded bg-secondary/50 px-2 py-0.5 text-xs font-medium text-muted-foreground">
                    {items.length} signal{items.length !== 1 ? 's' : ''}
                  </span>
                </div>
                {isGroupExpanded ? (
                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                )}
              </button>

              {isGroupExpanded && (
                <div className="divide-y divide-border/30 bg-card">
                  {items.map((insight) => {
                    const isExpanded = expandedArchiveSignalId === insight.id;
                    const isPositive =
                        insight.price_change_pct !== undefined &&
                        insight.price_change_pct !== null &&
                        insight.price_change_pct >= 0;
                    const timeString = insight.published_at
                      ? new Date(insight.published_at).toLocaleTimeString(
                        'en-US',
                        {
                          hour: '2-digit',
                          minute: '2-digit',
                        },
                      )
                      : '';

                    const isHighlighted = highlightedSignalId === insight.id;

                    return (
                      <div
                        key={insight.id}
                        id={`insight-card-${insight.id}`}
                        className={cn(
                          'p-4 sm:p-5 hover:bg-secondary/20 transition-all cursor-pointer text-left border-l-4 flex flex-col justify-center',
                          isExpanded && 'bg-secondary/10 border-l-[6px] shadow-md',
                          isHighlighted && 'ring-2 ring-indigo-500 ring-offset-2 dark:ring-offset-[#120F1D] animate-pulse shadow-[0_0_25px_rgba(212, 169, 79,0.6)]'
                        )}
                        onClick={() => setExpandedArchiveSignalId(
                          isExpanded ? null : insight.id,
                        )
                        }
                      >
                        <div className="flex items-center justify-between gap-4">
                          <div className="flex items-center gap-3">
                            <div className="flex h-8 w-12 shrink-0 items-center justify-center rounded-md bg-secondary/50 text-sm font-mono font-black text-foreground border border-border">
                              {insight.ticker || 'MKT'}
                            </div>
                            <div>
                              <h4 className="text-base md:text-lg font-bold text-foreground leading-snug line-clamp-1 sm:line-clamp-none">
                                {insight.key_event || insight.summary}
                              </h4>
                              <div className="flex items-center gap-2 mt-1 text-xs font-medium text-muted-foreground flex-wrap">
                                {insight.trend && (
                                  <span className={cn(
                                    'font-bold',
                                    insight.trend === 'Bullish' ? 'text-rose-500/90' : insight.trend === 'Bearish' ? 'text-red-500/90' : 'text-sky-500/90'
                                  )}>
                                    {insight.trend}
                                  </span>
                                )}
                                {insight.price_change_pct !== undefined && insight.price_change_pct !== null && (
                                  <>
                                    <span>•</span>
                                    <span className={cn('font-bold', isPositive ? 'text-rose-500' : 'text-red-500')}>
                                      {formatPriceChange(insight.price_change_pct)}
                                    </span>
                                  </>
                                )}
                                {timeString && (
                                  <>
                                    <span>•</span>
                                    <span>{timeString}</span>
                                  </>
                                )}
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 text-xs text-muted-foreground shrink-0">
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-muted-foreground" />
                            )}
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="mt-4 pt-4 border-t border-border/40 text-base space-y-4">
                            <p className="text-muted-foreground leading-relaxed text-sm md:text-base whitespace-pre-wrap">
                              {insight.summary}
                            </p>
                            <div className="flex flex-wrap gap-1.5 pt-1">
                              {insight.citations?.map((citation) => {
                                const faviconUrl = getFaviconUrl(citation);
                                const label = getShortLabel(citation);

                                return (
                                  <a
                                    key={citation}
                                    href={citation}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1 text-xs font-semibold text-muted-foreground hover:text-primary transition-all hover:bg-primary/5 hover:border-primary/20"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    {faviconUrl && (
                                      <img
                                        src={faviconUrl}
                                        alt={label}
                                        width={12}
                                        height={12}
                                        className="h-3 w-3 rounded-sm object-contain"
                                        onError={(e) => {
                                          (
                                              e.currentTarget as HTMLImageElement
                                          ).style.display = 'none';
                                        }}
                                      />
                                    )}
                                    {label}
                                    <ExternalLink className="h-2.5 w-2.5 opacity-60" />
                                  </a>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    )}
  </div>
);
