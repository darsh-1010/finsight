import { Sparkles, Lock } from 'lucide-react';
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

interface UpgradeModalProps {
  isOpen: boolean;
  onClose: () => void;
  requiredTierName?: string;
}

const UpgradeModal: React.FC<UpgradeModalProps> = ({ 
  isOpen, 
  onClose, 
  requiredTierName = 'Premium' 
}) => {
  const navigate = useNavigate();

  const handleUpgrade = () => {
    onClose();
    navigate(PROFILE_SUBSCRIPTION_PATH);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[425px] overflow-hidden border-primary/20">
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-3xl -mr-16 -mt-16" />
        <div className="absolute bottom-0 left-0 w-24 h-24 bg-blue-400/10 rounded-full blur-2xl -ml-12 -mb-12" />
        
        <DialogHeader className="relative z-10">
          <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mb-4 border border-primary/20">
            <Lock className="h-6 w-6 text-primary" />
          </div>
          <DialogTitle className="text-2xl font-bold">
            Upgrade Required
          </DialogTitle>
          <DialogDescription className="text-base pt-2 text-balance">
            You need to upgrade to access this lesson. This content is available for <span className="font-bold text-primary">{requiredTierName}</span> members and above.
          </DialogDescription>
        </DialogHeader>

        <div className="py-4 relative z-10 flex flex-col items-center justify-center">
            <div className="p-4 bg-primary/5 rounded-2xl border border-primary/10 w-full flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                    <Sparkles className="h-5 w-5 text-primary" />
                </div>
                <div className="text-sm">
                    <p className="font-bold text-foreground">Unlock Exclusive Content</p>
                    <p className="text-muted-foreground">Get access to all learning modules and advanced trading tools.</p>
                </div>
            </div>
        </div>

        <DialogFooter className="relative z-10 sm:justify-center gap-3">
          <Button 
            variant="ghost"
            onClick={onClose}
            className="flex-1 rounded-xl"
          >
            Maybe Later
          </Button>
          <Button 
            onClick={handleUpgrade} 
            className="flex-1 px-8 py-6 text-lg font-bold rounded-xl shadow-lg shadow-primary/20 hover:scale-[1.02] active:scale-[0.98] transition-all bg-primary"
          >
            Upgrade Now
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export { UpgradeModal };
