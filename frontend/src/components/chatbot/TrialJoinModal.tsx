import { useRouter } from 'next/navigation';
import React from 'react';
import { PiSparkleFill } from 'react-icons/pi';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';

interface TrialJoinModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const TrialJoinModal: React.FC<TrialJoinModalProps> = ({ isOpen, onClose }) => {
  const navigate = useRouter().push;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md bg-white dark:bg-[#08070A] border-gray-100 dark:border-gray-800 shadow-2xl rounded-3xl">
        <DialogHeader className="flex flex-col items-center pt-6">
          <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-6 animate-pulse">
            <PiSparkleFill className="text-primary text-3xl" />
          </div>
          <DialogTitle className="text-2xl font-bold text-center">
            Save Your Progress
          </DialogTitle>
          <DialogDescription className="text-center text-muted-foreground mt-4 text-base leading-relaxed">
            Your insights disappear when you leave. Join free and keep everything - forever.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex flex-col sm:flex-row gap-3 mt-8 pb-4">
          <Button
            variant="outline"
            className="w-full sm:w-1/2 py-6 text-lg rounded-xl border-gray-200 dark:border-gray-800"
            onClick={() => {
              onClose();
              navigate('/login');
            }}
          >
            Login
          </Button>
          <Button
            className="w-full sm:w-1/2 py-6 text-lg rounded-xl shadow-lg shadow-primary/20"
            onClick={() => {
              onClose();
              navigate('/signup');
            }}
          >
            Create free account
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default TrialJoinModal;
