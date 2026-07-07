import { CheckCircle2, Sparkles } from 'lucide-react';
import React from 'react';

import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../ui/dialog';

import { useAuth } from '@/context/AuthContext';
import { useAppSelector } from '@/store/hooks';
import { selectTiers } from '@/store/slices/tierSlice';

interface TierWelcomeModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const TierHighlights = ({ highlights, description }: { highlights?: string[], description?: string }) => (
  <div className="space-y-4">
    {highlights && highlights.length > 0 ? (
      highlights.map((highlight, index) => (
        <div key={index} className="flex items-start gap-3 group">
          <div className="mt-1 bg-green-500/10 text-green-500 rounded-full p-0.5 group-hover:bg-green-500 group-hover:text-white transition-colors duration-200">
            <CheckCircle2 className="h-4 w-4" />
          </div>
          <span className="text-sm font-medium text-muted-foreground group-hover:text-foreground transition-colors duration-200">
            {highlight}
          </span>
        </div>
      ))
    ) : (
      <p className="text-sm text-muted-foreground italic">
        {description || 'No specific highlights listed for this tier.'}
      </p>
    )}
  </div>
);

const TierWelcomeModal: React.FC<TierWelcomeModalProps> = ({ isOpen, onClose }) => {
  const { user } = useAuth();
  const tiers = useAppSelector(selectTiers);

  // Find the user's current tier details
  const tierName = user?.tier_name || 'Foundation';
  const currentTier = tiers.find(t => 
    t.name.toLowerCase().includes(tierName.toLowerCase()) || 
    tierName.toLowerCase().includes(t.name.toLowerCase())
  );

  if (!currentTier && isOpen && tiers.length > 0) {
    console.warn(`TierWelcomeModal: No matching tier found for "${tierName}"`, { availableTiers: tiers.map(t => t.name) });
  }

  if (!currentTier) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-125 overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-3xl -mr-16 -mt-16" />
        <div className="absolute bottom-0 left-0 w-24 h-24 bg-blue-400/10 rounded-full blur-2xl -ml-12 -mb-12" />
        
        <DialogHeader className="relative z-10">
          <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center mb-4 border border-primary/20">
            <Sparkles className="h-6 w-6 text-primary" />
          </div>
          <DialogTitle className="text-2xl font-bold flex items-center gap-2">
            Welcome to {currentTier.name}!
          </DialogTitle>
          <DialogDescription className="text-base pt-2">
            You are now subscribed to the <span className="font-bold text-foreground">{currentTier.name}</span> tier. 
            Here&apos;s everything you can do with your new plan:
          </DialogDescription>
        </DialogHeader>

        <div className="py-6 relative z-10">
          <TierHighlights highlights={currentTier.highlights} description={currentTier.description} />
        </div>

        <DialogFooter className="relative z-10 sm:justify-center">
          <Button 
            onClick={onClose} 
            className="w-full sm:w-auto px-8 py-6 text-lg font-bold rounded-xl shadow-lg shadow-primary/20 hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            Get Started
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export { TierWelcomeModal };
