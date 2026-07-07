/* eslint-disable max-lines-per-function */
import { Globe, ChevronRight, ExternalLink } from 'lucide-react';
import React from 'react';
import { useNavigate } from 'react-router-dom';

import type { ScrapingURLResponse } from '@/api/admin';
import { Skeleton } from '@/components/ui/skeleton';

interface ActivePipelinesProps {
  scrapingURLs: ScrapingURLResponse[];
  isScrapingURLsLoading: boolean;
}

const getDomainName = (urlStr: string): string => {
  try {
    const parsed = new URL(urlStr);

    return parsed.hostname.replace('www.', '');
  } catch {
    return urlStr;
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

const ActivePipelines: React.FC<ActivePipelinesProps> = ({
  scrapingURLs,
  isScrapingURLsLoading,
}) => {
  const navigate = useNavigate();

  return (
    <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-xs">
      <div className="p-6 border-b border-border flex items-center justify-between bg-secondary/5">
        <div>
          <h3 className="text-lg font-bold flex items-center gap-2">
            <Globe className="w-5 h-5 text-primary" /> Active Scraping Sources
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Manage automated targets, frequency configurations, and scrapers.
          </p>
        </div>
        <button
          onClick={() => navigate('/admin/scraping?tab=frequency')}
          className="text-xs text-primary font-bold hover:underline flex items-center gap-1"
        >
          Configure <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="p-6">
        {isScrapingURLsLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : scrapingURLs.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground text-sm">
            No scraping pipelines registered.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border text-xs text-muted-foreground font-semibold">
                  <th className="pb-3 pr-4">Pipeline Name</th>
                  <th className="pb-3 px-4">Domain</th>
                  <th className="pb-3 px-4">Frequency</th>
                  <th className="pb-3 pl-4 text-right">Latest Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {scrapingURLs.slice(0, 4).map((url) => (
                  <tr
                    key={url.id}
                    className="text-sm group hover:bg-secondary/5 transition-colors"
                  >
                    <td className="py-3.5 pr-4 font-semibold text-foreground">
                      {url.name}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-muted-foreground">
                      <a
                        href={url.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:underline flex items-center gap-1"
                      >
                        {getDomainName(url.url)}{' '}
                        <ExternalLink className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </a>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="text-xs font-semibold px-2 py-0.5 bg-secondary border border-border rounded-md text-muted-foreground uppercase">
                        {url.frequency_for_scrapping}
                      </span>
                    </td>
                    <td className="py-3.5 pl-4 text-right">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadgeStyles(
                          url.status || 'unknown'
                        )}`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            url.status?.toLowerCase() === 'completed'
                              ? 'bg-rose-500'
                              : url.status?.toLowerCase() === 'failed'
                                ? 'bg-rose-500'
                                : 'bg-indigo-500'
                          }`}
                        />
                        {url.status
                          ? url.status.charAt(0).toUpperCase() +
                            url.status.slice(1).replace('_', ' ')
                          : 'Idle'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default ActivePipelines;
