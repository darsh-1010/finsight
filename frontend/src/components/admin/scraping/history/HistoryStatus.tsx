import { RefreshCw, AlertCircle, Search } from 'lucide-react';


export const LoadingComponent = () => (
  <div className="flex flex-col items-center justify-center py-20 bg-white/50 dark:bg-gray-800/50 backdrop-blur-sm rounded-2xl border border-gray-100 dark:border-gray-700">
    <RefreshCw size={40} className="text-primary animate-spin mb-4" />
    <p className="text-muted-foreground font-medium">Loading job history...</p>
  </div>
);

export const ErrorComponent = ({
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

export const ZeroFilterDataComponent = () => (
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
