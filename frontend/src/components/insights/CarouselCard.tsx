import { ExternalLink, Lock, Zap } from 'lucide-react';
import Link from 'next/link';
import React from 'react';

import {
  formatPriceChange,
  getTrendStyle,
  getFaviconUrl,
  getShortLabel,
  getRelativeTime,
} from './helpers';
import type { MarketInsight } from './marketInsightTypes';

import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/utils';

interface CarouselCardProps {
  insight: MarketInsight;
  isActive: boolean;
  isHighlighted?: boolean;
}

export const CarouselCard: React.FC<CarouselCardProps> = ({
  insight,
  isActive,
  isHighlighted = false,
}) => {
  const { user } = useAuth();
  const trendStyle = getTrendStyle(insight.trend);
  const isPositive =
    insight.price_change_pct !== undefined &&
    insight.price_change_pct !== null &&
    insight.price_change_pct >= 0;

  const isLocked = user && user.tier_level < insight.tier_required;
  const relativeTime = getRelativeTime(
    insight.published_at || insight.created_at,
  );

  return (
    <article
      id={`insight-card-${insight.id}`}
      className={cn(
        'absolute inset-0 rounded-2xl border border-border bg-card text-left shadow-lg transition-all duration-500 overflow-hidden flex flex-col md:grid md:grid-cols-12',
        isActive
          ? 'opacity-100 scale-100 translate-x-0 z-10 pointer-events-auto'
          : 'opacity-0 scale-95 pointer-events-none z-0',
        isHighlighted &&
          'ring-2 ring-indigo-500 ring-offset-2 dark:ring-offset-[#120F1D] animate-pulse shadow-[0_0_25px_rgba(212, 169, 79,0.6)]',
      )}
    >
      {/* Sidebar Area: Trend & Ticker */}
      <div
        className={cn(
          'md:col-span-4 flex flex-row md:flex-col justify-between items-center md:items-start p-4 md:p-5 border-b md:border-b-0 md:border-r border-border/40 shrink-0',
          insight.trend === 'Bullish'
            ? 'bg-gradient-to-br from-rose-500/10 via-rose-500/5 to-transparent dark:from-rose-500/15 dark:via-rose-500/2'
            : insight.trend === 'Bearish'
              ? 'bg-gradient-to-br from-red-500/10 via-red-500/5 to-transparent dark:from-red-500/15 dark:via-red-500/2'
              : 'bg-gradient-to-br from-sky-500/10 via-sky-500/5 to-transparent dark:from-sky-500/15 dark:via-sky-500/2',
          isLocked ? 'blur-sm select-none opacity-50' : '',
        )}
      >
        {/* Ticker Emblem */}
        <div className="flex items-center gap-3 md:flex-col md:items-start md:gap-4 w-full md:h-full justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 md:h-12 md:w-12 text-sm shrink-0 items-center justify-center rounded-xl border border-border bg-background shadow-sm font-mono font-extrabold text-[#9C6F0E] tracking-wider">
              {insight.ticker || 'MKT'}
            </div>
            <div className="md:hidden flex flex-col">
              {insight.trend && (
                <span
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold',
                    trendStyle.labelClass,
                  )}
                >
                  {trendStyle.icon}
                  {insight.trend}
                </span>
              )}
            </div>
          </div>

          {/* Desktop specific middle container */}
          <div className="hidden md:flex flex-col gap-2 my-auto">
            {insight.trend && (
              <span
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold w-fit',
                  trendStyle.labelClass,
                )}
              >
                {trendStyle.icon}
                {insight.trend}
              </span>
            )}
            {insight.price_change_pct !== undefined &&
              insight.price_change_pct !== null && (
              <span
                className={cn(
                  'text-8xl font-bold tracking-tight',
                  isPositive ? 'text-rose-500' : 'text-red-500',
                )}
              >
                {formatPriceChange(insight.price_change_pct)}
              </span>
            )}
          </div>

          {/* Right/Bottom Info Badge */}
          <div className="flex items-center md:items-start gap-2 md:flex-col justify-end w-auto md:w-full">
            {/* Mobile price change */}
            {insight.price_change_pct !== undefined &&
              insight.price_change_pct !== null && (
              <span
                className={cn(
                  'md:hidden text-xs font-bold',
                  isPositive ? 'text-rose-500' : 'text-red-500',
                )}
              >
                {formatPriceChange(insight.price_change_pct)}
              </span>
            )}
            <span className="inline-flex items-center gap-1 rounded-full bg-[#9C6F0E]/10 text-[#9C6F0E] px-2.5 py-1 text-[10px] md:text-xs font-bold border border-[#9C6F0E]/20 shadow-[0_0_10px_rgba(156, 111, 14,0.1)]">
              <Zap className="h-3 w-3 fill-current" /> Top Signal
            </span>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div
        className={cn(
          'md:col-span-8 flex flex-col justify-between p-4 md:p-5 h-full space-y-4',
          isLocked ? 'blur-sm select-none opacity-50' : '',
        )}
      >
        <div className="space-y-2 md:space-y-2">
          {/* Key Event / Headline & Summary */}
          {insight.key_event ? (
            <>
              <h2 className="text-base md:text-4xl font-bold text-foreground leading-none tracking-tight">
                {insight.key_event}
              </h2>
              {insight.summary && insight.summary !== insight.key_event && (
                <p className="text-xs md:text-base leading-relaxed text-muted-foreground mt-4 whitespace-pre-wrap">
                  {insight.summary}
                </p>
              )}
            </>
          ) : (
            <p className="text-sm md:text-xl font-medium leading-relaxed text-foreground mt-4  whitespace-pre-wrap">
              {insight.summary}
            </p>
          )}
        </div>

        {/* Citations and Time */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-border/40">
          <span className="text-[10px] md:text-xs text-muted-foreground font-medium">
            {relativeTime}
          </span>

          <div className="flex flex-wrap gap-1.5">
            {insight.citations?.map((citation) => {
              const faviconUrl = getFaviconUrl(citation);
              const label = getShortLabel(citation);

              return (
                <a
                  key={citation}
                  href={citation}
                  target="_blank"
                  rel="noreferrer"
                  title={citation}
                  className="
    group inline-flex items-center gap-3
    rounded-2xl border border-border
    bg-card
    px-4 py-2.5
    text-sm font-medium text-card-foreground
    shadow-sm
    transition-all duration-300
    hover:-translate-y-1
    hover:border-primary/30
    hover:bg-primary/5
    hover:shadow-lg
    focus-visible:outline-none
    focus-visible:ring-2
    focus-visible:ring-primary/40
    focus-visible:ring-offset-2
  "
                >
                  {faviconUrl && (
                    <div
                      className="
        flex h-8 w-8 shrink-0 items-center justify-center
        rounded-lg border border-border
        bg-muted/40
        transition-colors
        group-hover:bg-background
      "
                    >
                      <img
                        src={faviconUrl}
                        alt={label}
                        width={18}
                        height={18}
                        className="h-4.5 w-4.5 object-contain"
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).style.display =
                            'none';
                        }}
                      />
                    </div>
                  )}

                  <div className="flex min-w-0 flex-col">
                    <span className="truncate font-semibold">{label}</span>
                    <span className="text-xs text-muted-foreground">
                      External Source
                    </span>
                  </div>

                  <ExternalLink
                    className="
      ml-auto h-4 w-4 shrink-0 text-muted-foreground
      transition-all duration-200
      group-hover:text-primary
      group-hover:translate-x-0.5
      group-hover:-translate-y-0.5
    "
                  />
                </a>
              );
            })}
          </div>
        </div>
      </div>

      {isLocked && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-background/60 backdrop-blur-md transition-all duration-300">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#9C6F0E]/10 text-[#9C6F0E] border border-[#9C6F0E]/20 shadow-[0_0_15px_rgba(156, 111, 14,0.2)] mb-2 animate-bounce">
            <Lock className="h-5 w-5" />
          </div>
          <h3 className="mb-3 text-base font-extrabold text-foreground tracking-tight">
            Premium Insight
          </h3>
          <Link
            href="/pricing"
            className="rounded-full bg-gradient-to-r from-[#D4A94F] to-[#9C6F0E] px-5 py-1.5 text-xs font-bold text-white shadow-md hover:shadow-[0_0_15px_rgba(212, 169, 79,0.4)] transition-all duration-200 hover:scale-105"
          >
            Upgrade to Unlock
          </Link>
        </div>
      )}
    </article>
  );
};
