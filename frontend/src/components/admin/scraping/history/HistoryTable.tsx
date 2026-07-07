import {
  Clock,
  Play,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
} from "lucide-react";


import { ZeroFilterDataComponent } from "./HistoryStatus";
import type { ScrapingJobHistory } from "../../../../hooks/ScrapingHistoryHooks";

import { cn } from "@/lib/utils";

export const getStatusIcon = (status: string) => {
  switch (status.toLowerCase()) {
    case "queued":
      return <Clock size={14} className="text-gray-400" />;
    case "started":
      return <Play size={14} className="text-blue-500" />;
    case "in_progress":
      return <Loader2 size={14} className="text-indigo-500 animate-spin" />;
    case "completed":
      return <CheckCircle size={14} className="text-green-500" />;
    case "failed":
      return <XCircle size={14} className="text-red-500" />;
    default:
      return <AlertCircle size={14} className="text-gray-400" />;
  }
};

export const getStatusStyle = (status: string) => {
  switch (status.toLowerCase()) {
    case "queued":
      return "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
    case "started":
      return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400";
    case "in_progress":
      return "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400";
    case "completed":
      return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400";
    case "failed":
      return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
    default:
      return "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
  }
};

export const formatDate = (dateStr?: string) => {
  if (!dateStr) return "N/A";
  try {
    const date = new Date(dateStr);

    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  } catch {
    return "Invalid date";
  }
};

export const formatStatusLabel = (status: string) =>
  status.charAt(0).toUpperCase() + status.slice(1).replace("_", " ");

export const TableHeaderComponent = () => (
  <thead className="sticky top-0 bg-white dark:bg-gray-900 z-10">
    <tr className="border-b border-gray-100 dark:border-gray-800">
      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Job Name / IDs
      </th>
      <th className="px-6 py-4 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Status
      </th>
      <th className="px-6 py-4 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Timing
      </th>
      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Details / Error
      </th>
    </tr>
  </thead>
);

export const JobInfo = ({ item }: { item: ScrapingJobHistory }) => (
  <div className="flex flex-col">
    <span className="text-sm font-semibold text-gray-900 dark:text-gray-100 leading-snug">
      {item.name}
    </span>
    <span className="text-[12px] text-muted-foreground font-mono mt-1">
      Job: {item.job_id}
    </span>
    <span className="text-[12px] text-muted-foreground font-mono">
      Run: {item.run_id}
    </span>
  </div>
);

export const StatusBadge = ({ status }: { status: string }) => (
  <div className="flex justify-center">
    <span
      className={cn(
        "inline-flex items-center w-30 gap-1.5 px-3 py-1 rounded-full text-xs font-medium border border-transparent shadow-xs",
        getStatusStyle(status),
      )}
    >
      {getStatusIcon(status)}
      {formatStatusLabel(status)}
    </span>
  </div>
);

export const TimeRow = ({
  label,
  value,
}: {
  label: string;
  value: string | undefined;
}) => (
  <div className="flex items-center justify-between gap-4">
    <span className="font-medium">{label}:</span>
    <span>{formatDate(value)}</span>
  </div>
);

export const JobTimeline = ({ item }: { item: ScrapingJobHistory }) => (
  <div className="flex flex-col gap-1.5 text-[12px] text-muted-foreground whitespace-nowrap">
    <TimeRow label="Queued" value={item.queued_at} />
    <TimeRow label="Started" value={item.started_at} />
    <TimeRow label="Completed" value={item.completed_at} />
  </div>
);

export const JobMessage = ({ item }: { item: ScrapingJobHistory }) => {
  if (item.error) {
    return (
      <div className="flex items-start gap-2 text-xs text-red-500 bg-red-50 dark:bg-red-900/10 p-2 rounded-lg border border-red-100 dark:border-red-900/20 max-w-md">
        <AlertCircle size={14} className="shrink-0 mt-0.5" />
        <span className="line-clamp-3">{item.error}</span>
      </div>
    );
  }

  if (item.status === "completed") {
    return (
      <span className="text-xs text-green-600 dark:text-green-400 font-medium">
        Job completed successfully.
      </span>
    );
  }

  return (
    <span className="text-xs text-muted-foreground italic">
      No details available.
    </span>
  );
};

export const TableRowComponent = ({ item }: { item: ScrapingJobHistory }) => (
  <tr className="group hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
    <td className="px-6 py-5">
      <JobInfo item={item} />
    </td>

    <td className="px-6 py-5">
      <StatusBadge status={item.status} />
    </td>

    <td className="px-6 py-5">
      <JobTimeline item={item} />
    </td>

    <td className="px-6 py-5">
      <div className="w-75">
        <JobMessage item={item} />
      </div>
    </td>
  </tr>
);

export const ContentBodyComponent = ({
  filteredData,
}: {
  filteredData: ScrapingJobHistory[];
}) => (
  <div className="bg-white dark:bg-gray-900/50 backdrop-blur-xl rounded-2xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
    {filteredData.length === 0 ? (
      <ZeroFilterDataComponent />
    ) : (
      <div className="overflow-x-auto">
        <div className="max-h-100 overflow-y-auto">
          <table className="w-full border-collapse min-w-200">
            <TableHeaderComponent />
            <tbody className="divide-y divide-gray-50 dark:divide-gray-800/50">
              {filteredData.map((item) => (
                <TableRowComponent key={item.id} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )}
  </div>
);
