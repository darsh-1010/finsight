/* eslint-disable max-lines-per-function */
import {  Save } from 'lucide-react';
import React from 'react';
import { FaRegComment } from 'react-icons/fa';

import type { InsightStatusChangeHandler } from './types';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import type { InsightResponse } from '@/store/apiSlice';


const StatusEditDialog: React.FC<{
  insight: InsightResponse;
  onStatusChange: InsightStatusChangeHandler;
  isUpdating: boolean;
   children?: React.ReactNode;
}> = ({ insight, onStatusChange, isUpdating }) => {
  const [open, setOpen] = React.useState(false);
  const [status, setStatus] = React.useState<InsightResponse['status']>(
    insight.status
  );
  const [reviewNotes, setReviewNotes] = React.useState('');

  React.useEffect(() => {
    if (!open) {
      setStatus(insight.status);
      setReviewNotes('');
    }
  }, [insight.status, open]);

  const submitStatusUpdate = () => {
    onStatusChange({
      entity_id: insight.id,
      status,
      review_notes: reviewNotes.trim() || null,
    });
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 rounded-md border border-border text-xs font-semibold text-muted-foreground hover:bg-secondary hover:text-foreground whitespace-nowrap shrink-0"
        >
          <FaRegComment className="h-3.5 w-3.5" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Update Insight Status</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-3">
            <span className="text-sm font-semibold text-muted-foreground block">
              Status
            </span>
            <div className="inline-flex rounded-lg border border-border bg-muted p-0.5 select-none">
              {[
                { value: 'draft', label: 'Draft' },
                { value: 'approved', label: 'Approve' },
                { value: 'rejected', label: 'Reject' },
              ].map((opt) => {
                const isActive = status === opt.value;

                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setStatus(opt.value as InsightResponse['status'])}
                    className={cn(
                      'px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer whitespace-nowrap',
                      isActive
                        ? opt.value === 'approved'
                          ? 'bg-rose-500 text-white font-bold shadow-sm'
                          : opt.value === 'rejected'
                            ? 'bg-red-500 text-white font-bold shadow-sm'
                            : 'bg-slate-500 text-white font-bold shadow-sm'
                        : 'text-muted-foreground hover:bg-secondary/80 hover:text-foreground'
                    )}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="space-y-2">
            <span className="text-sm font-semibold text-muted-foreground block">
              Review notes
            </span>
            <textarea
              value={reviewNotes}
              onChange={(event) => setReviewNotes(event.target.value)}
              rows={4}
              className="w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
              placeholder="Optional admin note"
            />
          </div>
        </div>

        <DialogFooter className="mt-2">
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button disabled={isUpdating} onClick={submitStatusUpdate}>
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default StatusEditDialog;
