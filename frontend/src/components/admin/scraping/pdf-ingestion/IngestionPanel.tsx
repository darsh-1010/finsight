import { FileUp, Link, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import React from 'react';

import { cn } from '@/lib/utils';

export type IngestionMode = 'file' | 'url';

export interface StatusState {
  type: 'idle' | 'loading' | 'success' | 'error';
  message: string;
}

const TabButton: React.FC<{
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}> = ({ active, onClick, icon, label }) => (
  <button
    onClick={onClick}
    className={cn(
      'flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-all rounded-xl border',
      active
        ? 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 shadow-sm text-primary'
        : 'border-transparent text-muted-foreground hover:bg-gray-100 dark:hover:bg-gray-800/50',
    )}
  >
    {icon}
    {label}
  </button>
);

const FileUploadZone: React.FC<{
  onSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  selectedFile: File | null;
}> = ({ onSelect, fileInputRef, selectedFile }) => (
  <div
    onClick={() => fileInputRef.current?.click()}
    className={cn(
      'border-2 border-dashed rounded-2xl py-6 flex flex-col items-center justify-center cursor-pointer transition-all group animate-in fade-in zoom-in-95 duration-300',
      selectedFile
        ? 'border-primary/50 bg-primary/5'
        : 'border-gray-200 dark:border-gray-800 hover:border-primary/50 hover:bg-primary/5',
    )}
  >
    <FileUp
      className={cn(
        'mb-3 transition-colors',
        selectedFile
          ? 'text-primary'
          : 'text-gray-400 group-hover:text-primary',
      )}
      size={40}
    />
    <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
      {selectedFile ? selectedFile.name : 'Click to browse or drag and drop'}
    </p>
    <p className="text-xs text-gray-400 mt-2">
      {selectedFile
        ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB`
        : 'PDF files only (max 10MB)'}
    </p>
    <input
      type="file"
      ref={fileInputRef}
      onChange={onSelect}
      className="hidden"
      accept="application/pdf"
    />
  </div>
);

const URLInputForm: React.FC<{
  url: string;
  setUrl: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
}> = ({ url, setUrl, onSubmit, isLoading }) => (
  <form
    onSubmit={onSubmit}
    className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300"
  >
    <div className="relative">
      <input
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://example.com/document.pdf"
        className="w-full bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-800 rounded-xl px-4 py-4 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all pl-12"
        required
      />
      <Link
        className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400"
        size={20}
      />
    </div>
    <button
      type="submit"
      disabled={isLoading}
      className="w-full bg-primary text-white py-4 rounded-xl font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-primary/20"
    >
      {isLoading ? (
        <span className="flex items-center justify-center gap-2">
          <Loader2 className="animate-spin" size={20} />
          Processing...
        </span>
      ) : (
        'Start Ingestion'
      )}
    </button>
  </form>
);

const StatusMessage: React.FC<{ status: StatusState }> = ({ status }) => {
  if (status.type === 'idle') return null;

  return (
    <div
      className={cn(
        'mt-6 p-4 rounded-xl text-sm flex items-center gap-3 animate-in fade-in slide-in-from-top-2 border',
        status.type === 'loading' &&
          'bg-blue-500/5 text-blue-500 border-blue-500/10',
        status.type === 'success' &&
          'bg-rose-500/5 text-rose-500 border-rose-500/10',
        status.type === 'error' &&
          'bg-red-500/5 text-red-500 border-red-500/10',
      )}
    >
      {status.type === 'loading' && (
        <Loader2 className="animate-spin" size={18} />
      )}
      {status.type === 'success' && <CheckCircle2 size={18} />}
      {status.type === 'error' && <AlertCircle size={18} />}
      {status.message}
    </div>
  );
};

interface IngestionPanelProps {
  mode: IngestionMode;
  setMode: (m: IngestionMode) => void;
  selectedFile: File | null;
  setSelectedFile: (f: File | null) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleUpload: () => void;
  status: StatusState;
  url: string;
  setUrl: (v: string) => void;
  executeScrape: (e: React.FormEvent) => void;
}

/* -------------------- Sub Components -------------------- */

const ModeTabs: React.FC<{
  mode: 'file' | 'url';
  setMode: (mode: 'file' | 'url') => void;
}> = ({ mode, setMode }) => (
  <div className="flex bg-gray-100/50 dark:bg-gray-800/50 p-1.5 rounded-2xl mb-8">
    <TabButton
      active={mode === 'file'}
      onClick={() => setMode('file')}
      icon={<FileUp size={18} />}
      label="Local File"
    />
    <TabButton
      active={mode === 'url'}
      onClick={() => setMode('url')}
      icon={<Link size={18} />}
      label="Remote URL"
    />
  </div>
);

const FileModeContent: React.FC<{
  selectedFile: File | null;
  setSelectedFile: (file: File | null) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleUpload: () => void;
  isLoading: boolean;
}> = ({
  selectedFile,
  setSelectedFile,
  fileInputRef,
  handleUpload,
  isLoading,
}) => (
  <div className="space-y-4">
    <FileUploadZone
      onSelect={(e) => setSelectedFile(e.target.files?.[0] || null)}
      fileInputRef={fileInputRef}
      selectedFile={selectedFile}
    />

    <button
      onClick={handleUpload}
      disabled={!selectedFile || isLoading}
      className="w-full bg-primary text-white py-3 rounded-xl font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-primary/20"
    >
      {isLoading ? (
        <span className="flex items-center justify-center gap-2">
          <Loader2 className="animate-spin" size={18} />
          Processing...
        </span>
      ) : (
        'Upload Document'
      )}
    </button>
  </div>
);

/* -------------------- Main Component -------------------- */

const IngestionPanel: React.FC<IngestionPanelProps> = ({
  mode,
  setMode,
  selectedFile,
  setSelectedFile,
  fileInputRef,
  handleUpload,
  status,
  url,
  setUrl,
  executeScrape,
}) => {
  const isLoading = status.type === 'loading';

  return (
    <div className="w-full md:w-95 flex-none">
      <ModeTabs mode={mode} setMode={setMode} />

      {mode === 'file' ? (
        <FileModeContent
          selectedFile={selectedFile}
          setSelectedFile={setSelectedFile}
          fileInputRef={fileInputRef}
          handleUpload={handleUpload}
          isLoading={isLoading}
        />
      ) : (
        <URLInputForm
          url={url}
          setUrl={setUrl}
          onSubmit={executeScrape}
          isLoading={isLoading}
        />
      )}

      <StatusMessage status={status} />
    </div>
  );
};

export default IngestionPanel;
