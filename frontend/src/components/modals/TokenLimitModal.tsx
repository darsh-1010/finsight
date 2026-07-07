import { AlertTriangle } from 'lucide-react';
import React from 'react';
import { useNavigate } from 'react-router-dom';

import { PROFILE_SUBSCRIPTION_PATH } from '@/lib/profileRoutes';

import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../ui/dialog';

interface TokenLimitModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const TokenLimitModal: React.FC<TokenLimitModalProps> = ({ 
  isOpen, 
  onClose, 
}) => {
  const navigate = useNavigate();

  const handleUpgrade = () => {
    navigate(PROFILE_SUBSCRIPTION_PATH);
    onClose();

  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[425px] overflow-hidden border-orange-500/20">
        <div className="absolute top-0 right-0 w-32 h-32 bg-orange-500/10 rounded-full blur-3xl -mr-16 -mt-16" />
        <div className="absolute bottom-0 left-0 w-24 h-24 bg-red-400/10 rounded-full blur-2xl -ml-12 -mb-12" />
        
        <DialogHeader className="relative z-10">
          <div className="w-12 h-12 bg-orange-500/10 rounded-xl flex items-center justify-center mb-4 border border-orange-500/20">
            <AlertTriangle className="h-6 w-6 text-orange-500" />
          </div>
          <DialogTitle className="text-2xl font-bold">
            Daily Token Limit Exceeded
          </DialogTitle>
          <DialogDescription className="text-base pt-2 text-balance">
            You have reached your daily limit for messages. Please wait until tomorrow for your tokens to refresh, or upgrade your plan for more capacity.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="relative z-10 sm:justify-end gap-3 mt-4">
          <Button 
            variant="ghost"
            onClick={onClose}
            className="flex-1 rounded-xl"
          >
            Okay
          </Button>
          <Button 
            onClick={handleUpgrade} 
            className="flex-1 px-8 py-6 text-lg font-bold rounded-xl shadow-lg shadow-orange-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all bg-orange-500 hover:bg-orange-600 text-white"
          >
            Upgrade Plan
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export { TokenLimitModal };
