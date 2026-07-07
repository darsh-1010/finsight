import {
  Search,
  Calendar,
  AlertCircle,
  RefreshCw,
  Clock,
  Play,
  CheckCircle,
  XCircle,
  Loader2,
  Database,
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

import api from '@/api/client';
import { cn } from '@/lib/utils';

interface ScrapingJobHistory {
  id: number;
  run_id: string;
  job_id: string;
  website_id: number;
  name: string;
  status: string;
  queued_at?: string;
  started_at?: string;
  in_progress_at?: string;
  completed_at?: string;
  error?: string;
}

const statuses = [
  'All Statuses',
  'Queued',
  'Started',
  'In_Progress',
  'Completed',
  'Failed',
];

const getStatusIcon = (status: string) => {
  switch (status.toLowerCase()) {
  case 'queued':
    return <Clock size={14} className="text-gray-400" />;
  case 'started':
    return <Play size={14} className="text-blue-500" />;
  case 'in_progress':
    return <Loader2 size={14} className="text-indigo-500 animate-spin" />;
  case 'completed':
    return <CheckCircle size={14} className="text-green-500" />;
  case 'failed':
    return <XCircle size={14} className="text-red-500" />;
  default:
    return <AlertCircle size={14} className="text-gray-400" />;
  }
};

const getStatusStyle = (status: string) => {
  switch (status.toLowerCase()) {
  case 'queued':
    return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
  case 'started':
    return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400';
  case 'in_progress':
    return 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400';
  case 'completed':
    return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400';
  case 'failed':
    return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
  default:
    return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
  }
};

const formatDate = (dateStr?: string) => {
  if (!dateStr) return 'N/A';
  try {
    const date = new Date(dateStr);

    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(date);
  } catch {
    return 'Invalid date';
  }
};

const getErrorMessage = (err: unknown): string => {
  const errorObj = err as { message?: string };

  return errorObj.message || 'Failed to fetch history. Please try again later.';
};

const filterScrapingHistory = (
  data: ScrapingJobHistory[],
  searchTerm: string,
  selectedStatus: string,
): ScrapingJobHistory[] => {
  const term = searchTerm.toLowerCase();

  return data.filter((item) => {
    const matchesSearch =
      item.name?.toLowerCase().includes(term) ||
      item.job_id?.toLowerCase().includes(term) ||
      item.run_id?.toLowerCase().includes(term);

    const matchesStatus =
      selectedStatus === 'All Statuses' ||
      item.status === selectedStatus.toLowerCase();

    return matchesSearch && matchesStatus;
  });
};

const useScrapingHistory = () => {
  const [data, setData] = useState<ScrapingJobHistory[]>([]);
  const [filteredData, setFilteredData] = useState<ScrapingJobHistory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('All Statuses');

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.get('/admin/scraping/history');

      setData(response.data);
      setFilteredData(response.data);
    } catch (err: unknown) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    setFilteredData(filterScrapingHistory(data, searchTerm, selectedStatus));
  }, [searchTerm, selectedStatus, data]);

  return {
    data,
    filteredData,
    isLoading,
    error,
    selectedStatus,
    searchTerm,
    setSearchTerm,
    setSelectedStatus,
    fetchData,
  };
};

const LoadingComponent = () => (
  <div className="flex flex-col items-center justify-center py-20 bg-white/50 dark:bg-gray-800/50 backdrop-blur-sm rounded-2xl border border-gray-100 dark:border-gray-700">
    <RefreshCw size={40} className="text-primary animate-spin mb-4" />
    <p className="text-muted-foreground font-medium">Loading job history...</p>
  </div>
);

const ErrorComponent = ({
  fetchData,
  error,
}: {
  fetchData: () => Promise<void>;
  error: string;
}) => (
  <div className="flex flex-col items-center justify-center py-20 bg-red-50 dark:bg-red-900/10 rounded-2xl border border-red-100 dark:border-red-900/30 text-center px-4">
    <AlertCircle size={48} className="text-red-500 mb-4" />
    <h3 className="text-lg font-semibold text-red-900 dark:text-red-400 mb-2">
      Failed to load history
    </h3>
    <p className="text-red-700 dark:text-red-300 max-w-md mb-6">{error}</p>
    <button
      onClick={fetchData}
      className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl transition-colors font-medium"
    >
      Try Again
    </button>
  </div>
);

const HeaderComponent = ({
  searchTerm,
  selectedStatus,
  setSelectedStatus,
  setSearchTerm,
}: {
  searchTerm: string;
  selectedStatus: string;
  setSelectedStatus: (status: string) => void;
  setSearchTerm: (term: string) => void;
}) => (
  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
    <div className="relative group flex-1">
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted-foreground group-focus-within:text-primary transition-colors">
        <Search size={18} />
      </div>
      <input
        type="text"
        placeholder="Search by job name, ID, or run ID..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all text-sm"
      />
    </div>

    <div className="relative w-48">
      <select
        value={selectedStatus}
        onChange={(e) => setSelectedStatus(e.target.value)}
        className="w-full h-full pl-4 pr-10 py-2.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all text-sm appearance-none cursor-pointer"
      >
        {statuses.map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </select>
      <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-muted-foreground border-l border-gray-100 dark:border-gray-800 ml-2 pl-2">
        <Database size={14} />
      </div>
    </div>
  </div>
);

const ZeroFilterDataComponent = () => (
  <div className="flex flex-col items-center justify-center py-20 text-center px-4">
    <div className="w-16 h-16 bg-gray-50 dark:bg-gray-800 rounded-full flex items-center justify-center mb-4">
      <Search size={24} className="text-gray-400" />
    </div>
    <h3 className="text-lg font-medium mb-1">No history found</h3>
    <p className="text-muted-foreground text-sm max-w-xs">
      Try adjusting your search terms or filters.
    </p>
  </div>
);

const TableHeaderComponent = () => (
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
const formatStatusLabel = (status: string) => status.charAt(0).toUpperCase() + status.slice(1).replace('_', ' ');

const JobInfo = ({ item }: { item: ScrapingJobHistory }) => (
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

const StatusBadge = ({ status }: { status: string }) => (
  <div className="flex justify-center">
    <span
      className={cn(
        'inline-flex items-center w-30 gap-1.5 px-3 py-1 rounded-full text-xs font-medium border border-transparent shadow-xs',
        getStatusStyle(status),
      )}
    >
      {getStatusIcon(status)}
      {formatStatusLabel(status)}
    </span>
  </div>
);

const TimeRow = ({
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

const JobTimeline = ({ item }: { item: ScrapingJobHistory }) => (
  <div className="flex flex-col gap-1.5 text-[12px] text-muted-foreground whitespace-nowrap">
    <TimeRow label="Queued" value={item.queued_at} />
    <TimeRow label="Started" value={item.started_at} />
    <TimeRow label="Completed" value={item.completed_at} />
  </div>
);

const JobMessage = ({ item }: { item: ScrapingJobHistory }) => {
  if (item.error) {
    return (
      <div className="flex items-start gap-2 text-xs text-red-500 bg-red-50 dark:bg-red-900/10 p-2 rounded-lg border border-red-100 dark:border-red-900/20 max-w-md">
        <AlertCircle size={14} className="shrink-0 mt-0.5" />
        <span className="line-clamp-3">{item.error}</span>
      </div>
    );
  }

  if (item.status === 'completed') {
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

const TableRowComponent = ({ item }: { item: ScrapingJobHistory }) => (
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

const ContentBodyComponent = ({
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

const ScrapingHistory: React.FC = () => {
  const {
    data,
    selectedStatus,
    searchTerm,
    filteredData,
    isLoading,
    error,
    setSearchTerm,
    setSelectedStatus,
    fetchData,
  } = useScrapingHistory();

  if (isLoading) {
    return <LoadingComponent />;
  }

  if (error) {
    return <ErrorComponent error={error} fetchData={fetchData} />;
  }

  return (
    <div className="space-y-6">
      <HeaderComponent
        searchTerm={searchTerm}
        selectedStatus={selectedStatus}
        setSearchTerm={setSearchTerm}
        setSelectedStatus={setSelectedStatus}
      />
      <ContentBodyComponent filteredData={filteredData} />

      <div className="flex items-center justify-between text-xs text-muted-foreground px-2">
        <p>
          Showing {filteredData.length} of {data.length} jobs
        </p>
        <p className="flex items-center gap-1">
          <Calendar size={12} />
          History is kept for all past scraping executions
        </p>
      </div>
    </div>
  );
};

export default ScrapingHistory;
