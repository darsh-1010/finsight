import {
  Search,
  ExternalLink,

  Globe,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

import api from '@/api/client';

/* Logical part */

interface ScrapingSubURL {
  id: number;
  scraping_url_id: number;
  source: string;
  url: string;
  title: string;
  summary?: string;
  published_date?: string;
  scraped_at?: string;
  scraper_version?: string;
}

const extractUniqueSources = (items: ScrapingSubURL[]): string[] => {
  const sources = items.map((item) => item.source);

  return Array.from(new Set(sources)).filter(Boolean).sort() as string[];
};

const filterScrapingData = (
  data: ScrapingSubURL[],
  searchTerm: string,
  selectedSource: string,
): ScrapingSubURL[] => {
  const term = searchTerm.toLowerCase();

  return data.filter((item) => {
    const matchesSearch =
      item.title?.toLowerCase().includes(term) ||
      item.source?.toLowerCase().includes(term) ||
      item.url?.toLowerCase().includes(term);

    const matchesSource =
      selectedSource === 'All Sources' || item.source === selectedSource;

    return matchesSearch && matchesSource;
  });
};

const formatDate = (dateStr?: string): string => {
  if (!dateStr) return 'N/A';

  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(dateStr));
  } catch {
    return 'Invalid date';
  }
};

const getErrorMessage = (err: unknown): string => {
  const errorObj = err as { message?: string };

  return errorObj.message || 'Failed to fetch content. Please try again later.';
};

const useScrapingContent = () => {
  const [data, setData] = useState<ScrapingSubURL[]>([]);
  const [filteredData, setFilteredData] = useState<ScrapingSubURL[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSource, setSelectedSource] = useState('All Sources');
  const [uniqueSources, setUniqueSources] = useState<string[]>([]);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await api.get('/admin/scraping/sub-urls');

      setData(response.data);
      setFilteredData(response.data);
      setUniqueSources(extractUniqueSources(response.data));
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
    setFilteredData(filterScrapingData(data, searchTerm, selectedSource));
  }, [searchTerm, selectedSource, data]);

  return {
    formatDate,
    filteredData,
    isLoading,
    error,
    setSearchTerm,
    setSelectedSource,
    uniqueSources,
    fetchData,
    data,
    searchTerm,
    selectedSource,
  };
};

/* Static part */

interface DateCellProps {
  date?: string;
  formatDate: (dateStr?: string) => string;
}

interface TableRowComponentProps {
  item: ScrapingSubURL;
  formatDate: (dateStr?: string) => string;
}

const LoadingComponent = () => (
  <div className="flex flex-col items-center justify-center py-20 bg-white/50 dark:bg-gray-800/50 backdrop-blur-sm rounded-2xl border border-gray-100 dark:border-gray-700">
    <RefreshCw size={40} className="text-primary animate-spin mb-4" />
    <p className="text-muted-foreground font-medium">
      Crunching scraped data...
    </p>
  </div>
);

const ErrorComponent = ({
  error,
  fetchData,
}: {
  error: string;
  fetchData: () => Promise<void>;
}) => (
  <div className="flex flex-col items-center justify-center py-20 bg-red-50 dark:bg-red-900/10 rounded-2xl border border-red-100 dark:border-red-900/30 text-center px-4">
    <AlertCircle size={48} className="text-red-500 mb-4" />
    <h3 className="text-lg font-semibold text-red-900 dark:text-red-400 mb-2">
      Connection Issue
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
  setSearchTerm,
  selectedSource,
  setSelectedSource,
  uniqueSources,
}: {
  searchTerm: string;
  setSearchTerm: (value: string) => void;
  selectedSource: string;
  setSelectedSource: (value: string) => void;
  uniqueSources: string[];
}) => (
  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
    <div className="relative group flex-1">
      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted-foreground group-focus-within:text-primary transition-colors">
        <Search size={18} />
      </div>
      <input
        type="text"
        placeholder="Search by title, source, or URL..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        className="w-full pl-10 pr-4 py-2.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all text-sm"
      />
    </div>

    <div className="relative w-48">
      <select
        value={selectedSource}
        onChange={(e) => setSelectedSource(e.target.value)}
        className="w-full h-full pl-4 pr-10 py-2.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all text-sm appearance-none cursor-pointer"
      >
        <option value="All Sources">All Sources</option>
        {uniqueSources.map((source: string) => (
          <option key={source} value={source}>
            {source}
          </option>
        ))}
      </select>
      <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-muted-foreground border-l border-gray-100 dark:border-gray-800 ml-2 pl-2">
        <Globe size={14} />
      </div>
    </div>
  </div>
);

const TableRowComponent = ({ item, formatDate }: TableRowComponentProps) => (
  <tr className="group hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
    <td className="px-6 py-5">
      <div className="flex flex-col max-w-base">
        <span className="text-sm font-semibold text-gray-900 dark:text-gray-100 line-clamp-2 leading-snug mb-1">
          {item.title}
        </span>
      </div>
    </td>

    <td className="px-6 py-5">
      <div className="flex items-center justify-center gap-2">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {item.source}
        </span>
      </div>
    </td>

    <td className="px-6 py-5">
      <DateCell date={item.scraped_at} formatDate={formatDate} />
    </td>

    <td className="px-6 py-5">
      {item.published_date ? (
        <DateCell date={item.published_date} formatDate={formatDate} />
      ) : null}
    </td>

    <td className="px-6 py-5 text-center">
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center justify-center p-2 text-primary hover:bg-primary/10 rounded-lg transition-colors group-hover:scale-110"
        title="View Original Source"
      >
        <ExternalLink size={18} />
      </a>
    </td>
  </tr>
);

const DateCell = ({ date, formatDate }: DateCellProps) => (
  <div className="flex flex-col gap-1 w-[180px]">
    <div className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
      {/* <Calendar size={12} /> */}
      <span>{formatDate(date)}</span>
    </div>
  </div>
);

const TableHeaderComponent = () => (
  <thead className="sticky top-0 bg-white dark:bg-gray-900 z-10">
    <tr className="border-b border-gray-100 dark:border-gray-800">
      <th className="px-6 py-4 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Content
      </th>
      <th className="px-6 py-4 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Source
      </th>
      <th className="px-6 py-4 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Scraped At
      </th>
      <th className="px-6 py-4 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Published At
      </th>
      <th className="px-6 py-4 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Actions
      </th>
    </tr>
  </thead>
);

const BodyContent = ({
  filteredData,
  formatDate,
}: {
  filteredData: ScrapingSubURL[];
  formatDate: (dateStr?: string) => string;
}) => (
  <div className="bg-white dark:bg-gray-900/50 backdrop-blur-xl rounded-2xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
    {filteredData.length === 0 ? (
      <div className="flex flex-col items-center justify-center py-20 text-center px-4">
        <div className="w-16 h-16 bg-gray-50 dark:bg-gray-800 rounded-full flex items-center justify-center mb-4">
          <Search size={24} className="text-gray-400" />
        </div>
        <h3 className="text-lg font-medium mb-1">No matches found</h3>
        <p className="text-muted-foreground text-sm max-w-xs">
          Try adjusting your search terms or verify if the sources have been
          scraped recently.
        </p>
      </div>
    ) : (
      <div className="overflow-x-auto">
        <div className="max-h-100 overflow-y-auto">
          <table className="w-full border-collapse min-w-200">
            <TableHeaderComponent />
            <tbody className="divide-y divide-gray-50 dark:divide-gray-800/50">
              {filteredData.map((item: ScrapingSubURL) => (
                <TableRowComponent
                  key={item.id}
                  formatDate={formatDate}
                  item={item}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )}
  </div>
);

const ScrapingContent: React.FC = () => {
  const {
    formatDate,
    filteredData,
    isLoading,
    error,
    setSearchTerm,
    setSelectedSource,
    uniqueSources,
    fetchData,
    data,
    searchTerm,
    selectedSource,
  } = useScrapingContent();

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
        selectedSource={selectedSource}
        setSelectedSource={setSelectedSource}
        setSearchTerm={setSearchTerm}
        uniqueSources={uniqueSources}
      />
      <BodyContent formatDate={formatDate} filteredData={filteredData} />

      <div className="flex items-center justify-between text-xs text-muted-foreground px-2">
        <p>
          Showing {filteredData.length} of {data.length} entries
        </p>
        <p className="flex items-center gap-1">
          <AlertCircle size={12} />
          Content is updated automatically based on set frequencies
        </p>
      </div>
    </div>
  );
};

export default ScrapingContent;
