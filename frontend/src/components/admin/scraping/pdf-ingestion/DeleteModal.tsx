import { AlertCircle } from 'lucide-react';
import React from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface DeleteModalProps {
  showDeleteModal: boolean;
  setShowDeleteModal: (show: boolean) => void;
  confirmDelete: () => void;
}

const DeleteModal: React.FC<DeleteModalProps> = ({
  showDeleteModal,
  setShowDeleteModal,
  confirmDelete,
}) => (
  <Dialog open={showDeleteModal} onOpenChange={setShowDeleteModal}>
    <DialogContent className="sm:max-w-md">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2 text-red-500">
          <AlertCircle size={24} />
          Confirm Deletion
        </DialogTitle>
        <DialogDescription className="pt-2">
          Are you sure you want to delete this document? This action cannot be
          undone and will permanently remove the file from S3 storage.
        </DialogDescription>
      </DialogHeader>
      <DialogFooter className="mt-4 gap-2 sm:gap-0">
        <Button
          variant="outline"
          onClick={() => setShowDeleteModal(false)}
          className="rounded-xl"
        >
          Cancel
        </Button>
        <Button
          variant="destructive"
          onClick={confirmDelete}
          className="rounded-xl"
        >
          Delete Permanently
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

export default DeleteModal;
