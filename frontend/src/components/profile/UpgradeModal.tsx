import { Loader2, ArrowRight, X } from 'lucide-react';
import { useRouter } from 'next/navigation';
import React, { useState, useEffect } from 'react';

import { selectTier } from '@/api/payments';
import PricingCards from '@/components/pricing/PricingCards';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { useAuth } from '@/context/AuthContext';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import {
  fetchTiers,
  selectTiers,
  selectTiersLoading,
  selectIsFallback,
} from '@/store/slices/tierSlice';

const handleUnauthenticatedRedirect = (
  navigate: (path: string) => void,
  tierLevel: number,
) => {
  navigate(`/signup?tier=${tierLevel}`);
};

interface UpgradeModalProps {
  isLoadingAuth?: boolean;
  isCancelingAtPeriodEnd?: boolean;
  scheduledTierLevel?: number | null;
}

const UpgradeModal: React.FC<UpgradeModalProps> = ({
  isLoadingAuth = false,
  isCancelingAtPeriodEnd = false,
  scheduledTierLevel = null
}) => {
  const { user } = useAuth();
  const navigate = useRouter().push;
  const dispatch = useAppDispatch();

  const [open, setOpen] = useState(false);
  const [submittingTier, setSubmittingTier] = useState<number | null>(null);
  const [successState, setSuccessState] = useState<{type: 'upgrade' | 'downgrade' | 'cancel' | 'resume', tierName: string} | null>(null);
  const [errorState, setErrorState] = useState<string | null>(null);

  const [pendingAction, setPendingAction] = useState<{
    tierLevel: number;
    tierIndex: number;
    actionType: 'upgrade' | 'downgrade' | 'resume' | 'subscribe';
    tierName: string;
  } | null>(null);

  const tiers = useAppSelector(selectTiers);
  const isLoading = useAppSelector(selectTiersLoading);
  const isFallback = useAppSelector(selectIsFallback);

  useEffect(() => {
    if (open && tiers.length === 0) {
      dispatch(fetchTiers());
    } else if (!open) {
      setSuccessState(null);
      setErrorState(null);
      setPendingAction(null);
    }
  }, [open, dispatch, tiers.length]);

  const handleSubscribe = async (tierLevel: number, tierIndex: number) => {
    if (!user) {
      handleUnauthenticatedRedirect(navigate, tierLevel);

      return;
    }
    const tier = tiers.find((t) => t.level === tierLevel);

    if (!tier) return;

    let actionType: 'upgrade' | 'downgrade' | 'resume' | 'subscribe' = 'upgrade';

    if (tierLevel === user.tier_level) {
      actionType = 'resume';
    } else if (user.tier_level === 1) {
      actionType = 'subscribe';
    } else if (tierLevel > user.tier_level) {
      actionType = 'upgrade';
    } else {
      actionType = 'downgrade';
    }

    setPendingAction({ tierLevel, tierIndex, actionType, tierName: tier.name });
  };

  const executeSubscribe = async () => {
    if (!pendingAction || !user) return;
    const { tierLevel, tierIndex, actionType, tierName } = pendingAction;

    setPendingAction(null);
    setSubmittingTier(tierIndex);
    setErrorState(null);

    try {
      await selectTier(tierLevel);
      setSuccessState({ type: actionType === 'subscribe' ? 'upgrade' : actionType, tierName });
    } catch (e: any) {
      console.error('Tier switch error:', e);
      const msg = e.response?.data?.detail || 'Failed to switch plans. Please try again.';

      setErrorState(msg);
    }

    setSubmittingTier(null);
  };

  return (
    <Dialog open={open} onOpenChange={(val) => {
      if (submittingTier !== null) return;
      if (!val && successState) {
        window.location.reload();
      } else {
        setOpen(val);
      }
    }}>
      <DialogTrigger asChild>
        <Button
          disabled={isLoadingAuth}
          className="w-full h-[46px] bg-primary hover:bg-blue-600 text-white font-bold rounded-xl shadow-md shadow-primary/20 group transition-all duration-300 text-sm"
        >
          {isLoadingAuth ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <>
              Change Plan
              <ArrowRight
                size={16}
                className="ml-2 group-hover:translate-x-1 transition-transform"
              />
            </>
          )}
        </Button>
      </DialogTrigger>
      <DialogContent
        hideCloseButton={submittingTier !== null}
        onInteractOutside={(e) => submittingTier !== null && e.preventDefault()}
        onEscapeKeyDown={(e) => submittingTier !== null && e.preventDefault()}
        className="w-[95vw] max-w-[95vw] xl:w-[90vw] xl:max-w-[90vw] bg-background border-border max-h-[95vh] overflow-y-auto p-4 md:p-6 rounded-3xl shadow-2xl"
      >
        {/* Processing Overlay Loader */}
        {submittingTier !== null && (
          <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-background/70 backdrop-blur-md rounded-3xl">
            <div className="bg-card p-6 rounded-2xl shadow-xl flex flex-col items-center max-w-sm border border-border/50">
              <Loader2 className="w-12 h-12 text-primary animate-spin mb-4" />
              <h3 className="text-xl font-bold text-foreground text-center">Processing...</h3>
              <p className="text-sm text-muted-foreground mt-2 text-center">
                Please wait while we switch your plan.
              </p>
            </div>
          </div>
        )}

        <DialogHeader className="mb-2">
          <DialogTitle className="text-2xl font-bold text-center">
            Choose Your Plan
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col items-center">
          <div className="w-full">
            <PricingCards
              isLoading={isLoading}
              isFallback={isFallback}
              handleSubscribe={handleSubscribe}
              tiers={tiers}
              submittingTier={submittingTier}
              currentTierLevel={user?.tier_level}
              isCancelingAtPeriodEnd={isCancelingAtPeriodEnd}
              scheduledTierLevel={scheduledTierLevel}
            />
          </div>
        </div>
      </DialogContent>

      {/* Success Alert Dialog */}
      <AlertDialog open={!!successState} onOpenChange={(open) => {
        if (!open) window.location.reload();
      }}>
        <AlertDialogContent className="rounded-3xl max-w-md flex flex-col items-center text-center">
          <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center mb-2 mt-4">
            <svg className="w-10 h-10 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <AlertDialogHeader className="flex flex-col items-center">
            <AlertDialogTitle className="text-2xl font-bold text-center">
              Plan Updated
            </AlertDialogTitle>
            <AlertDialogDescription className="text-base text-left text-muted-foreground mt-2">
              You are now on the <span className="font-bold text-primary">{successState?.tierName}</span> plan.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-6 w-full sm:justify-center">
            <AlertDialogAction
              onClick={() => window.location.reload()}
              className="bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl h-12 w-full max-w-[200px]"
            >
              Done
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Error Alert Dialog */}
      <AlertDialog open={!!errorState} onOpenChange={(open) => !open && setErrorState(null)}>
        <AlertDialogContent className="rounded-3xl max-w-md flex flex-col items-center text-center">
          <button
            onClick={() => setErrorState(null)}
            className="absolute top-4 right-4 p-2 rounded-full hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
          >
            <X size={20} />
          </button>
          <div className="w-20 h-20 bg-red-500/10 rounded-full flex items-center justify-center mb-2 mt-4">
            <svg className="w-10 h-10 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <AlertDialogHeader className="flex flex-col items-center">
            <AlertDialogTitle className="text-2xl font-bold">
              Update Failed
            </AlertDialogTitle>
            <AlertDialogDescription className="text-base text-muted-foreground mt-2 px-2">
              {errorState}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-6 w-full sm:justify-center">
            <AlertDialogAction
              onClick={() => setErrorState(null)}
              className="bg-red-500 hover:bg-red-600 text-white rounded-xl h-12 w-full max-w-[200px] border-none"
            >
              Try Again
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Confirmation Alert Dialog */}
      <AlertDialog open={!!pendingAction} onOpenChange={(open) => !open && setPendingAction(null)}>
        <AlertDialogContent className="rounded-3xl max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl capitalize">
              Confirm {pendingAction?.actionType}?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-base text-left mt-2">
              {pendingAction?.actionType === 'resume' ? (
                `Are you sure you want to resume the ${pendingAction?.tierName} plan?`
              ) : pendingAction?.actionType === 'downgrade' ? (
                `Are you sure you want to downgrade to the ${pendingAction?.tierName} plan? This takes effect immediately.`
              ) : pendingAction?.actionType === 'subscribe' ? (
                `You are about to switch to the ${pendingAction?.tierName} plan.`
              ) : (
                `Are you sure you want to upgrade to the ${pendingAction?.tierName} plan?`
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-6">
            <AlertDialogCancel className="rounded-xl h-12 px-6">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={executeSubscribe}
              className="bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl h-12 px-6"
            >
              Confirm
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  );
};

export default UpgradeModal;
