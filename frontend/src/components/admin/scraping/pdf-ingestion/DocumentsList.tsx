import { Loader2, Trash2 } from 'lucide-react';
import React from 'react';

import type { IngestedPDFMetadata } from '@/api/admin';

const IngestedTableRow = ({
  pdf,
  onView,
  onDelete,
  isDeleting,
}: {
  pdf: IngestedPDFMetadata;
  onView: (pdf: IngestedPDFMetadata) => void;
  onDelete: (id: string) => void;
  isDeleting: boolean;
}) => (
  <tr className="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
    <td
      className="px-6 py-4 font-medium text-gray-700 dark:text-gray-300 truncate max-w-50"
      title={pdf.name}
    >
      {pdf.name}
    </td>
    <td className="px-6 py-4 text-right">
      <div className="flex items-center justify-end gap-3">
        <button
          onClick={() => onView(pdf)}
          className="text-primary hover:underline font-medium inline-flex items-center gap-1"
        >
          View
        </button>
        <button
          onClick={() => onDelete(pdf.id)}
          disabled={isDeleting}
          className="text-red-500 hover:text-red-600 transition-colors disabled:opacity-50"
          title="Delete document"
        >
          {isDeleting ? (
            <Loader2 className="animate-spin" size={18} />
          ) : (
            <Trash2 size={18} />
          )}
        </button>
      </div>
    </td>
  </tr>
);

const IngestedPDFTable: React.FC<{
  pdfs: IngestedPDFMetadata[];
  isLoading: boolean;
  onView: (pdf: IngestedPDFMetadata) => void;
  onDelete: (id: string) => void;
  deletingId: string | null;
}> = ({ pdfs, isLoading, onView, onDelete, deletingId }) => {
  if (isLoading && pdfs.length === 0) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="animate-spin text-primary" size={32} />
      </div>
    );
  }

  if (pdfs.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground border-2 border-dashed rounded-2xl border-gray-100 dark:border-gray-800">
        No documents ingested yet.
      </div>
    );
  }

  return (
    <div className="mt-8 overflow-x-auto rounded-2xl border border-gray-200 dark:border-gray-800 max-h-70">
      <table className="w-full text-left text-sm min-w-125">
        <thead className="bg-gray-50 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400 font-medium">
          <tr>
            <th className="px-6 py-4">Name</th>
            <th className="px-6 py-4 text-right">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {pdfs.map((pdf) => (
            <IngestedTableRow
              key={pdf.id}
              pdf={pdf}
              onView={onView}
              onDelete={onDelete}
              isDeleting={deletingId === pdf.id}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
};

interface DocumentsListProps {
  ingestedPdfs: IngestedPDFMetadata[];
  isFetching: boolean;
  onView: (pdf: IngestedPDFMetadata) => void;
  onDelete: (id: string) => void;
  deletingId: string | null;
}

const DocumentsList: React.FC<DocumentsListProps> = ({
  ingestedPdfs,
  isFetching,
  onView,
  onDelete,
  deletingId,
}) => (
  <div className="w-full flex-1 border-t md:border-t-0 md:border-l border-gray-100 dark:border-gray-800 pt-8 md:pt-0 md:pl-8 min-h-100 md:min-h-112.5">
    <h3 className="text-xl font-semibold mb-6 flex items-center gap-2">
      Ingested Documents
      <span className="text-sm font-normal px-3 py-1 bg-gray-100 dark:bg-gray-800 rounded-full text-gray-500">
        {ingestedPdfs.length}
      </span>
    </h3>
    <IngestedPDFTable
      pdfs={ingestedPdfs}
      isLoading={isFetching}
      onView={onView}
      onDelete={onDelete}
      deletingId={deletingId}
    />
  </div>
);

export default DocumentsList;
