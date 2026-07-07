import type { InsightResponse } from '@/store/apiSlice';

export const insightStatuses: InsightResponse['status'][] = [
  'draft',
  'approved',
  'rejected',
  'archived',
];

export const statusStyles: Record<InsightResponse['status'], string> = {
  draft: 'bg-slate-500/10 text-slate-700 ring-slate-500/20 dark:text-slate-300',
  approved: 'bg-green-500/10 text-green-700 ring-green-500/20 dark:text-green-400',
  rejected: 'bg-red-500/10 text-red-700 ring-red-500/20 dark:text-red-400',
  archived: 'bg-zinc-500/10 text-zinc-700 ring-zinc-500/20 dark:text-zinc-300',
};

export const formatDate = (value?: string | null) => {
  if (!value) return 'Not set';

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
};
