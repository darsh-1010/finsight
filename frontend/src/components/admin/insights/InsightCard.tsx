/* eslint-disable max-lines-per-function */
import { Eye } from 'lucide-react';
import type React from 'react';
import { useState } from 'react';

import StatusEditDialog from './StatusEditDialog';
import type { InsightStatusChangeHandler } from './types';
import { formatDate } from './utils';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import type { InsightResponse } from '@/store/apiSlice';

const InsightCard: React.FC<{
  insight: InsightResponse;
  onStatusChange: InsightStatusChangeHandler;
  isUpdating: boolean;
}> = ({ insight, onStatusChange, isUpdating }) => {
  const [open, setOpen] = useState(false);

  return (
    <div className="group flex items-center gap-4 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-secondary/10">
      {/* Ticker Box */}
      <div className="flex flex-col items-center justify-center h-14 w-14 shrink-0 rounded-lg bg-secondary/30 border border-border">
        <span className="text-[10px] font-bold text-[#9683C2] uppercase">
          {insight.ticker || 'MKT'}
        </span>
        {insight.price_change_pct !== null &&
          insight.price_change_pct !== undefined && (
          <span
            className={cn(
              'text-[10px] font-bold',
              insight.price_change_pct >= 0
                ? 'text-rose-500'
                : 'text-red-500',
            )}
          >
            {insight.price_change_pct > 0 ? '+' : ''}
            {insight.price_change_pct.toFixed(1)}%
          </span>
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 min-w-0 flex flex-col justify-center">
        <h2 className="text-sm font-bold text-foreground line-clamp-1">
          {insight.alert_message || insight.summary || 'Untitled insight'}
        </h2>
        <p className="mt-1 text-[13px] text-muted-foreground line-clamp-1">
          {insight.key_event || insight.summary}
        </p>

        {/* Tags Row */}
        <div className="mt-2.5 flex flex-wrap items-center gap-3 text-[11px] font-medium text-muted-foreground/80">
          <span className="rounded bg-secondary/50 px-2 py-0.5 text-foreground">
            Tier {insight.tier_required}
          </span>
          <span className="rounded bg-secondary/50 px-2 py-0.5 text-foreground capitalize">
            {insight.trend_type === 'weekly' ? 'Weekly' : 'Daily'}
          </span>
          {insight.price_change_pct !== null &&
            insight.price_change_pct !== undefined && (
            <span className="rounded bg-[#9683C2]/10 text-[#9683C2] px-2 py-0.5 font-bold">
              {insight.price_change_pct.toFixed(2)}%
            </span>
          )}
          <span>Created {formatDate(insight.created_at)}</span>
          {insight.published_at && (
            <span className="hidden sm:inline">
              · Published {formatDate(insight.published_at)}
            </span>
          )}
          {insight.expires_at && (
            <span className="hidden lg:inline">
              · Expires {formatDate(insight.expires_at)}
            </span>
          )}
        </div>
      </div>

      {/* Right Actions Box */}
      <div className="flex shrink-0 items-center justify-end gap-1.5 sm:gap-3 ml-2 sm:ml-4 w-[215px] sm:w-[290px]">
        {/* Hover-reveal Admin Review trigger */}
        <div className="max-w-0 opacity-0 group-hover:max-w-[40px] group-hover:opacity-100 transition-all duration-300 ease-in-out overflow-hidden shrink-0 pointer-events-none group-hover:pointer-events-auto">
          <StatusEditDialog
            insight={insight}
            onStatusChange={onStatusChange}
            isUpdating={isUpdating}
          />
        </div>
        {/* Segmented Switch Control */}
        <div className="inline-flex rounded-lg border border-border bg-secondary/30 p-0.5 select-none shrink-0">
          {[
            { value: 'draft', label: 'Draft' },
            { value: 'approved', label: 'Approve' },
            { value: 'rejected', label: 'Reject' },
          ].map((opt) => {
            const isActive = insight.status === opt.value;

            return (
              <button
                key={opt.value}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onStatusChange({
                    entity_id: insight.id,
                    status: opt.value as InsightResponse['status'],
                  });
                }}
                disabled={isUpdating}
                className={cn(
                  'px-1.5 sm:px-3 py-0.5 sm:py-1 text-[10px] sm:text-xs font-semibold rounded-md transition-all cursor-pointer whitespace-nowrap',
                  isActive
                    ? opt.value === 'approved'
                      ? 'bg-rose-500 text-white font-bold shadow-sm'
                      : opt.value === 'rejected'
                        ? 'bg-red-500 text-white font-bold shadow-sm'
                        : 'bg-slate-500 text-white font-bold shadow-sm'
                    : 'text-muted-foreground hover:bg-secondary/80 hover:text-foreground',
                )}
              >
                {opt.label}
              </button>
            );
          })}
        </div>

        {/* View Dialog Button */}
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-8 rounded-md border border-border text-xs font-semibold text-muted-foreground hover:bg-secondary hover:text-foreground shrink-0"
            >
              <Eye className="h-3.5 w-3.5 sm:mr-2" />
              <span className="hidden sm:inline">View</span>
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="leading-snug">
                {insight.alert_message || 'Insight Summary'}
              </DialogTitle>
            </DialogHeader>
            <div className="mt-4 space-y-4 text-sm text-foreground">
              {/* Status Section in View Modal */}
              <div className="rounded-lg border border-border p-4 bg-secondary/10">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <h4 className="font-semibold text-muted-foreground uppercase text-[10px] tracking-wider">
                      Status Review
                    </h4>
                    <p className="text-xs text-muted-foreground">
                      Approve, reject, or mark as draft from here.
                    </p>
                  </div>
                  <div className="inline-flex rounded-lg border border-border bg-muted p-0.5 select-none shrink-0 self-start sm:self-center">
                    {[
                      { value: 'draft', label: 'Draft' },
                      { value: 'approved', label: 'Approve' },
                      { value: 'rejected', label: 'Reject' },
                    ].map((opt) => {
                      const isActive = insight.status === opt.value;

                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => {
                            onStatusChange({
                              entity_id: insight.id,
                              status: opt.value as InsightResponse['status'],
                            });
                            setOpen(false); // Close modal
                          }}
                          disabled={isUpdating}
                          className={cn(
                            'px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer whitespace-nowrap',
                            isActive
                              ? opt.value === 'approved'
                                ? 'bg-rose-500 text-white font-bold shadow-sm'
                                : opt.value === 'rejected'
                                  ? 'bg-red-500 text-white font-bold shadow-sm'
                                  : 'bg-slate-500 text-white font-bold shadow-sm'
                              : 'text-muted-foreground hover:bg-secondary/80 hover:text-foreground',
                          )}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {insight.key_event && (
                <div>
                  <h4 className="font-semibold text-muted-foreground uppercase text-[10px] tracking-wider mb-1">
                    Key Event
                  </h4>
                  <p className="leading-relaxed">{insight.key_event}</p>
                </div>
              )}
              {insight.summary && (
                <div>
                  <h4 className="font-semibold text-muted-foreground uppercase text-[10px] tracking-wider mb-1">
                    Summary
                  </h4>
                  <p className="leading-relaxed whitespace-pre-wrap">
                    {insight.summary}
                  </p>
                </div>
              )}
              {insight.citations && insight.citations.length > 0 && (
                <div>
                  <h4 className="font-semibold text-muted-foreground uppercase text-[10px] tracking-wider mb-1">
                    Citations
                  </h4>
                  <ul className="list-disc pl-4 space-y-1">
                    {insight.citations.map((c, i) => (
                      <li key={i}>
                        <a
                          href={c}
                          target="_blank"
                          rel="noreferrer"
                          className="text-primary hover:underline break-all"
                        >
                          {c}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default InsightCard;
