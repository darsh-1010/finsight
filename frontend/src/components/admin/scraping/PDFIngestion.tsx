import React, { useRef, useState, useEffect } from 'react';

import DeleteModal from './pdf-ingestion/DeleteModal';
import DocumentsList from './pdf-ingestion/DocumentsList';
import IngestionPanel, {
  type IngestionMode,
  type StatusState,
} from './pdf-ingestion/IngestionPanel';

import { adminApi, type IngestedPDFMetadata } from '@/api/admin';
import { PDFViewerModal } from '@/components/common/PDFViewerModal';

// -------------------- Helpers --------------------

const getErrorMessage = (err: unknown, fallback: string) => {
  const axiosErr = err as { response?: { data?: { detail?: string } } };

  return axiosErr.response?.data?.detail || fallback;
};

// -------------------- Hooks --------------------

// Fetch PDFs Hook
const usePdfs = () => {
  const [ingestedPdfs, setIngestedPdfs] = useState<IngestedPDFMetadata[]>([]);
  const [isFetching, setIsFetching] = useState(false);

  const fetchPdfs = async () => {
    setIsFetching(true);
    try {
      const data = await adminApi.getIngestedPDFs();

      setIngestedPdfs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsFetching(false);
    }
  };

  useEffect(() => {
    void fetchPdfs();
  }, []);

  return { ingestedPdfs, isFetching, fetchPdfs };
};

// Upload + Scrape Hook
const useIngestionActions = (fetchPdfs: () => Promise<void>) => {
  const [status, setStatus] = useState<StatusState>({
    type: 'idle',
    message: '',
  });

  const handleUpload = async (
    selectedFile: File | null,
    setSelectedFile: (file: File | null) => void,
  ) => {
    if (!selectedFile) return;

    setStatus({ type: 'loading', message: 'Uploading document...' });

    try {
      await adminApi.uploadPDF(selectedFile);
      setStatus({ type: 'success', message: 'Document ingested!' });
      setSelectedFile(null);
      fetchPdfs();
    } catch (err) {
      setStatus({
        type: 'error',
        message: getErrorMessage(err, 'Upload failed.'),
      });
    }
  };

  const executeScrape = async (
    e: React.FormEvent,
    url: string,
    setUrl: (url: string) => void,
  ) => {
    e.preventDefault();
    if (!url) return;

    setStatus({ type: 'loading', message: 'Scraping source...' });

    try {
      await adminApi.scrapeURL(url);
      setStatus({ type: 'success', message: 'URL ingested!' });
      setUrl('');
      fetchPdfs();
    } catch (err) {
      setStatus({
        type: 'error',
        message: getErrorMessage(err, 'Scraping failed.'),
      });
    }
  };

  return { status, setStatus, handleUpload, executeScrape };
};

// Delete + View Hook
const usePdfActions = (fetchPdfs: () => Promise<void>) => {
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [pdfToDelete, setPdfToDelete] = useState<string | null>(null);

  const [showViewModal, setShowViewModal] = useState(false);
  const [pdfToView, setPdfToView] = useState<IngestedPDFMetadata | null>(null);

  const handleDelete = (id: string) => {
    setPdfToDelete(id);
    setShowDeleteModal(true);
  };

  const confirmDelete = async () => {
    if (!pdfToDelete) return;

    setDeletingId(pdfToDelete);

    try {
      await adminApi.deleteIngestedPDF(pdfToDelete);
      fetchPdfs();
    } catch (err) {
      console.error(err);
    } finally {
      setDeletingId(null);
      setShowDeleteModal(false);
      setPdfToDelete(null);
    }
  };

  const handleView = (pdf: IngestedPDFMetadata) => {
    setPdfToView(pdf);
    setShowViewModal(true);
  };

  return {
    deletingId,
    showDeleteModal,
    setShowDeleteModal,
    handleDelete,
    confirmDelete,
    showViewModal,
    setShowViewModal,
    pdfToView,
    handleView,
  };
};

// Main Hook (NOW SMALL ✅)
const useIngestion = () => {
  const { ingestedPdfs, isFetching, fetchPdfs } = usePdfs();

  const [mode, setMode] = useState<IngestionMode>('file');
  const [url, setUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const { status, handleUpload, executeScrape } =
    useIngestionActions(fetchPdfs);

  const pdfActions = usePdfActions(fetchPdfs);

  return {
    mode,
    setMode,
    url,
    setUrl,
    selectedFile,
    setSelectedFile,
    status,
    handleUpload: () => handleUpload(selectedFile, setSelectedFile),
    executeScrape: (e: React.FormEvent) => executeScrape(e, url, setUrl),
    ingestedPdfs,
    isFetching,
    ...pdfActions,
  };
};

// -------------------- Types --------------------

interface IngestionLayoutProps {
  mode: IngestionMode;
  setMode: React.Dispatch<React.SetStateAction<IngestionMode>>;
  url: string;
  setUrl: (url: string) => void;
  selectedFile: File | null;
  setSelectedFile: (file: File | null) => void;
  status: StatusState;
  handleUpload: () => void;
  executeScrape: (e: React.FormEvent) => void;
  ingestedPdfs: IngestedPDFMetadata[];
  isFetching: boolean;
  handleView: (pdf: IngestedPDFMetadata) => void;
  handleDelete: (id: string) => void;
  deletingId: string | null;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
}

// -------------------- UI --------------------

const IngestionLayout: React.FC<IngestionLayoutProps> = ({
  mode,
  setMode,
  url,
  setUrl,
  selectedFile,
  setSelectedFile,
  status,
  handleUpload,
  executeScrape,
  ingestedPdfs,
  isFetching,
  handleView,
  handleDelete,
  deletingId,
  fileInputRef,
}) => (
  <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
    <div className="bg-white/40 dark:bg-gray-900/40 backdrop-blur-2xl border border-gray-200 dark:border-gray-800 rounded-3xl p-6 md:p-8 shadow-xl flex flex-col md:flex-row gap-8">
      <IngestionPanel
        mode={mode}
        setMode={setMode}
        selectedFile={selectedFile}
        setSelectedFile={setSelectedFile}
        fileInputRef={fileInputRef}
        handleUpload={handleUpload}
        status={status}
        url={url}
        setUrl={setUrl}
        executeScrape={executeScrape}
      />

      <DocumentsList
        ingestedPdfs={ingestedPdfs}
        isFetching={isFetching}
        onView={handleView}
        onDelete={handleDelete}
        deletingId={deletingId}
      />
    </div>
  </div>
);

// -------------------- Main --------------------

const PDFIngestion = () => {
  const ingestion = useIngestion();
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <IngestionLayout {...ingestion} fileInputRef={fileInputRef} />

      <DeleteModal
        showDeleteModal={ingestion.showDeleteModal}
        setShowDeleteModal={ingestion.setShowDeleteModal}
        confirmDelete={ingestion.confirmDelete}
      />

      <PDFViewerModal
        isOpen={ingestion.showViewModal}
        onOpenChange={ingestion.setShowViewModal}
        url={ingestion.pdfToView?.url}
        title={ingestion.pdfToView?.name}
      />
    </>
  );
};

export default PDFIngestion;
