import { Plus, Upload, RefreshCw, Info } from 'lucide-react';
import React from 'react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

type HeaderProps = {
  isUploading: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  openCreateModal: () => void;
};

const HeaderTitle = () => (
  <div className="flex flex-col gap-4">
    <div>
      <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
        Brokers Management
      </h1>
      <p className="text-sm md:text-base text-muted-foreground mt-2">
        Manage brokers, their redirect URLs, and bulk import via CSV.
      </p>
    </div>
  </div>
);

const UploadButton = ({
  isUploading,
  onClick,
}: {
  isUploading: boolean;
  onClick: () => void;
}) => (
  <button
    onClick={onClick}
    disabled={isUploading}
    className="
      flex items-center gap-2 px-4 py-2
      bg-white dark:bg-gray-800
      border border-gray-200 dark:border-gray-700
      rounded-xl
      hover:bg-gray-50 dark:hover:bg-gray-800/80
      transition-colors text-sm font-medium
    "
  >
    {isUploading ? (
      <RefreshCw size={16} className="animate-spin" />
    ) : (
      <Upload size={16} />
    )}
    Upload CSV
  </button>
);

const HeaderActions = ({
  isUploading,
  fileInputRef,
  handleFileUpload,
  openCreateModal,
}: HeaderProps) => {
  const handleUploadClick = () => fileInputRef.current?.click();

  return (
    <div className="flex gap-3 items-center">
      <input
        type="file"
        accept=".csv"
        className="hidden"
        ref={fileInputRef}
        onChange={handleFileUpload}
      />

      <div className="flex items-center gap-1">
        <UploadButton isUploading={isUploading} onClick={handleUploadClick} />
        
        <Popover>
          <PopoverTrigger asChild>
            <button 
              className="p-2 text-muted-foreground hover:text-primary transition-colors rounded-full hover:bg-primary/10 flex-shrink-0 cursor-pointer"
              title="CSV Upload Guidelines"
            >
              <Info size={18} />
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-80 p-4" align="end">
            <h3 className="text-sm font-semibold text-primary mb-2">CSV Upload Guidelines</h3>
            <ul className="text-xs text-muted-foreground list-disc list-inside space-y-1.5">
              <li><strong>Format:</strong> <code className="bg-muted px-1 py-0.5 rounded border">.csv</code> (Comma-separated values)</li>
              <li><strong>Required Columns:</strong> <code className="bg-muted px-1 py-0.5 rounded border">name</code>, <code className="bg-muted px-1 py-0.5 rounded border">redirect_url</code></li>
              <li>Ensure the header row exactly matches the required column names.</li>
            </ul>
          </PopoverContent>
        </Popover>
      </div>

      <button
        onClick={openCreateModal}
        className="
          flex items-center gap-2 px-4 py-2
          bg-primary text-primary-foreground
          rounded-xl hover:bg-primary/90
          transition-colors text-sm font-medium
        "
      >
        <Plus size={16} />
        Add Broker
      </button>
    </div>
  );
};

const BrokerHeader = (props: HeaderProps) => (
  <div
    className="
      flex flex-col md:flex-row md:items-center
      justify-between gap-4
    "
  >
    <HeaderTitle />
    <HeaderActions {...props} />
  </div>
);

export default BrokerHeader;
