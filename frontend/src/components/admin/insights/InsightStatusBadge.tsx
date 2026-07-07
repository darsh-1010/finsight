import type React from 'react';

import { cn } from '@/lib/utils';
import type { InsightResponse } from '@/store/apiSlice';

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

const InsightStatusBadge: React.FC<{
  status: InsightResponse['status'] | string;
  className?: string;
}> = ({ status, className }) => (
  <span
    className={cn(
      'inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold capitalize',
      className
    )}
  >
    <span className={cn('h-1.5 w-1.5 rounded-full', getStatusColor(status))} />
    {status}
  </span>
);

export default InsightStatusBadge;
