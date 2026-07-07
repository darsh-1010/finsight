/* eslint-disable max-lines-per-function */
import { Globe, FileText, AlertCircle, Activity, ChevronRight } from 'lucide-react';
import React from 'react';
import { useNavigate } from 'react-router-dom';

import { Skeleton } from '@/components/ui/skeleton';

interface MetricsGridProps {
  totalPipelines: number;
  isScrapingURLsLoading: boolean;
  totalArticles: number;
  isScrapingSubURLsLoading: boolean;
  pendingReviewCount: number;
  isInsightsLoading: boolean;
  successRate: number;
  isScrapingHistoryLoading: boolean;
}

const MetricsGrid: React.FC<MetricsGridProps> = ({
  totalPipelines,
  isScrapingURLsLoading,
  totalArticles,
  isScrapingSubURLsLoading,
  pendingReviewCount,
  isInsightsLoading,
  successRate,
  isScrapingHistoryLoading,
}) => {
  const navigate = useNavigate();

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* Metric Card 1 */}
      <div
        onClick={() => navigate('/admin/scraping?tab=frequency')}
        className="p-6 bg-card border border-border/80 rounded-2xl relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-lg hover:shadow-primary/5 hover:border-primary/30 cursor-pointer group"
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] uppercase font-bold text-muted-foreground tracking-wider">
              Scraping Sources
            </p>
            {isScrapingURLsLoading ? (
              <Skeleton className="h-8 w-20 mt-2" />
            ) : (
              <h3 className="text-2xl font-extrabold mt-1 group-hover:text-primary transition-colors">
                {totalPipelines} <span className="text-xs text-muted-foreground font-medium">Active</span>
              </h3>
            )}
          </div>
          <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-500 group-hover:bg-blue-500 group-hover:text-white transition-all duration-300 shadow-inner">
            <Globe className="w-5 h-5" />
          </div>
        </div>
        <p className="text-[10px] text-muted-foreground mt-4 flex items-center gap-1 group-hover:underline">
          Manage targets and scheduling <ChevronRight className="w-3 h-3" />
        </p>
      </div>

      {/* Metric Card 2 */}
      <div
        onClick={() => navigate('/admin/scraping?tab=content')}
        className="p-6 bg-card border border-border/80 rounded-2xl relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-lg hover:shadow-violet-500/5 hover:border-violet-500/30 cursor-pointer group"
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] uppercase font-bold text-muted-foreground tracking-wider">
              Scraped Articles
            </p>
            {isScrapingSubURLsLoading ? (
              <Skeleton className="h-8 w-20 mt-2" />
            ) : (
              <h3 className="text-2xl font-extrabold mt-1 group-hover:text-violet-500 transition-colors">
                {totalArticles} <span className="text-xs text-muted-foreground font-medium">Items</span>
              </h3>
            )}
          </div>
          <div className="w-12 h-12 rounded-xl bg-violet-500/10 flex items-center justify-center text-violet-500 group-hover:bg-violet-500 group-hover:text-white transition-all duration-300 shadow-inner">
            <FileText className="w-5 h-5" />
          </div>
        </div>
        <p className="text-[10px] text-muted-foreground mt-4 flex items-center gap-1 group-hover:underline">
          Browse ingested content base <ChevronRight className="w-3 h-3" />
        </p>
      </div>

      {/* Metric Card 3 */}
      <div
        onClick={() => navigate('/admin/insights')}
        className="p-6 bg-card border border-border/80 rounded-2xl relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-lg hover:shadow-indigo-500/5 hover:border-indigo-500/30 cursor-pointer group"
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] uppercase font-bold text-muted-foreground tracking-wider">
              Pending Review
            </p>
            {isInsightsLoading ? (
              <Skeleton className="h-8 w-20 mt-2" />
            ) : (
              <h3 className="text-2xl font-extrabold mt-1 group-hover:text-indigo-500 transition-colors flex items-center gap-2">
                {pendingReviewCount}
                {pendingReviewCount > 0 && (
                  <span className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-ping" />
                )}
              </h3>
            )}
          </div>
          <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center text-indigo-500 group-hover:bg-indigo-500 group-hover:text-white transition-all duration-300 shadow-inner">
            <AlertCircle className="w-5 h-5" />
          </div>
        </div>
        <p className="text-[10px] text-muted-foreground mt-4 flex items-center gap-1 group-hover:underline">
          Review and publish insights <ChevronRight className="w-3 h-3" />
        </p>
      </div>

      {/* Metric Card 4 */}
      <div
        onClick={() => navigate('/admin/scraping?tab=history')}
        className="p-6 bg-card border border-border/80 rounded-2xl relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-lg hover:shadow-rose-500/5 hover:border-rose-500/30 cursor-pointer group"
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] uppercase font-bold text-muted-foreground tracking-wider">
              Pipeline Health
            </p>
            {isScrapingHistoryLoading ? (
              <Skeleton className="h-8 w-20 mt-2" />
            ) : (
              <h3 className="text-2xl font-extrabold mt-1 group-hover:text-rose-500 transition-colors">
                {successRate.toFixed(1)}% <span className="text-[10px] text-muted-foreground font-semibold">Success</span>
              </h3>
            )}
          </div>
          <div className="w-12 h-12 rounded-xl bg-rose-500/10 flex items-center justify-center text-rose-500 group-hover:bg-rose-500 group-hover:text-white transition-all duration-300 shadow-inner">
            <Activity className="w-5 h-5" />
          </div>
        </div>
        <p className="text-[10px] text-muted-foreground mt-4 flex items-center gap-1 group-hover:underline">
          Audit history & status logs <ChevronRight className="w-3 h-3" />
        </p>
      </div>
    </div>
  );
};

export default MetricsGrid;
