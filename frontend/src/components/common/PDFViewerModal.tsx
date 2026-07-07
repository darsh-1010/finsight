import React from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface PDFViewerModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  url?: string;
  title?: string;
}

export const PDFViewerModal: React.FC<PDFViewerModalProps> = ({
  isOpen,
  onOpenChange,
  url,
  title,
}) => (
  <Dialog open={isOpen} onOpenChange={onOpenChange}>
    <DialogContent className="sm:max-w-5xl h-[90vh] flex flex-col p-4">
      <DialogHeader className="flex-none px-2 pt-8">
        <DialogTitle className="flex items-center justify-between gap-4 py-2">
          <span className="truncate pr-8">{title || 'PDF Preview'}</span>
          <Button
            variant="outline"
            size="sm"
            asChild
            className="rounded-xl hidden sm:flex"
          >
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
            >
                Open in New Tab
            </a>
          </Button>
        </DialogTitle>
      </DialogHeader>
      <div className="flex-1 bg-gray-100 dark:bg-gray-800/50 rounded-xl overflow-hidden relative group">
        {url ? (
          <iframe
            src={`${url}#toolbar=0`}
            className="w-full h-full border-none"
            title={title || 'PDF Document'}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
              Failed to load PDF preview.
          </div>
        )}
      </div>
    </DialogContent>
  </Dialog>
);
