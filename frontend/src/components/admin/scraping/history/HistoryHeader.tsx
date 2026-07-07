import { Search, Database } from "lucide-react";


import { statuses } from "../../../../hooks/ScrapingHistoryHooks";

export const HeaderComponent = ({
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
