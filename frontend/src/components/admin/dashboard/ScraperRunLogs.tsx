/* eslint-disable max-lines-per-function */
import { Clock } from 'lucide-react';
import { useRouter } from 'next/navigation';
import React from 'react';

import { Skeleton } from '@/components/ui/skeleton';
import type { ScrapingJobHistory } from '@/store/apiSlice';

interface ScraperRunLogsProps {
  scrapingHistory: ScrapingJobHistory[];
  isScrapingHistoryLoading: boolean;
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

const getStatusBadgeStyles = (status: string) => {
  const normalized = status.toLowerCase();

  if (normalized === 'completed' || normalized === 'success') {
    return 'bg-rose-500/10 text-rose-500 border-rose-500/20';
  }
  if (normalized === 'failed') {
    return 'bg-rose-500/10 text-rose-500 border-rose-500/20';
  }
  if (normalized === 'in_progress' || normalized === 'started' || normalized === 'running') {
    return 'bg-indigo-500/10 text-indigo-500 border-indigo-500/20';
  }

  return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
};

const ScraperRunLogs: React.FC<ScraperRunLogsProps> = ({
  scrapingHistory,
  isScrapingHistoryLoading,
}) => {
  const navigate = useRouter().push;

  return (
    <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-xs">
      <div className="p-6 border-b border-border flex items-center justify-between bg-secondary/5">
        <div>
          <h3 className="text-lg font-bold flex items-center gap-2">
            <Clock className="w-5 h-5 text-violet-500" /> Scraper Run Logs
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Track actual system execution tasks.
          </p>
        </div>
        <button
          onClick={() => navigate('/admin/scraping?tab=history')}
          className="text-xs text-primary font-bold hover:underline"
        >
          Audit Log
        </button>
      </div>

      <div className="p-6 divide-y divide-border/60">
        {isScrapingHistoryLoading ? (
          <div className="space-y-3 py-2">
            <Skeleton className="h-12 w-full rounded-lg" />
            <Skeleton className="h-12 w-full rounded-lg" />
            <Skeleton className="h-12 w-full rounded-lg" />
          </div>
        ) : scrapingHistory.length === 0 ? (
          <div className="text-center py-6 text-xs text-muted-foreground">
            No job history available.
          </div>
        ) : (
          scrapingHistory.slice(0, 3).map((job) => (
            <div key={job.id} className="py-3 first:pt-0 last:pb-0">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-foreground line-clamp-1">
                  {job.name}
                </p>
                <span className={`text-[9px] uppercase font-black px-2 py-0.5 rounded-full border ${getStatusBadgeStyles(job.status)}`}>
                  {job.status}
                </span>
              </div>

              <div className="flex items-center justify-between text-[10px] text-muted-foreground mt-1">
                <span className="font-mono">
                  Run: {job.run_id}
                </span>
                <span>
                  {formatDate(job.completed_at || job.started_at)}
                </span>
              </div>

              {job.error && (
                <div className="mt-2 p-2 bg-rose-500/5 border border-rose-500/10 rounded-lg text-[10px] text-rose-500 font-medium leading-relaxed break-words">
                  Error: {job.error}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default ScraperRunLogs;
