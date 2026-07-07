import React from 'react';
import { useNavigate } from 'react-router-dom';
import { PiLockFill } from 'react-icons/pi';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

interface TrialLimitModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const TrialLimitModal: React.FC<TrialLimitModalProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md bg-white dark:bg-[#08070A] border-gray-100 dark:border-gray-800 shadow-2xl rounded-3xl">
        <DialogHeader className="flex flex-col items-center pt-6">
          <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-6 animate-pulse">
            <PiLockFill className="text-primary text-3xl" />
          </div>
          <DialogTitle className="text-2xl font-bold text-center">
            Continue Your Journey
          </DialogTitle>
          <DialogDescription className="text-center text-muted-foreground mt-4 text-base leading-relaxed">
            You&apos;ve reached the 5-message trial limit. Join FinSight to continue exploring deep market insights and professional investing intelligence.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="flex flex-col sm:flex-row gap-3 mt-8 pb-4">
          <Button
            variant="outline"
            className="w-full sm:w-1/2 py-6 text-lg rounded-xl border-gray-200 dark:border-gray-800"
            onClick={() => navigate('/login')}
          >
            Log In
          </Button>
          <Button
            className="w-full sm:w-1/2 py-6 text-lg rounded-xl shadow-lg shadow-primary/20"
            onClick={() => navigate('/signup')}
          >
            Get Full Access
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default TrialLimitModal;
