import { Loader2, ArrowRight, X } from 'lucide-react';
import { useRouter } from 'next/navigation';
import React, { useState, useEffect } from 'react';

import { createCheckoutSession, type PreviewSubscriptionResponse } from '@/api/payments';
import PricingCards from '@/components/pricing/PricingCards';
import PricingSwitch from '@/components/pricing/PricingSwitch';
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
import type { PricingTier } from '@/lib/interfaces/Pricing';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import {
  fetchTiers,
  selectTiers,
  selectTiersLoading,
  selectIsFallback,
} from '@/store/slices/tierSlice';

const getPriceId = (
  tier: PricingTier,
  billingPeriod: 'monthly' | 'yearly',
) => billingPeriod === 'monthly'
  ? tier.price_id
  : tier.yearly_price_id;

const startCheckout = async (priceId: string) => {
  const successUrl = `${window.location.origin}/payment-success`;
  const cancelUrl = `${window.location.origin}/pricing`;

  const { checkout_url } = await createCheckoutSession(
    priceId,
    successUrl,
    cancelUrl,
  );

  window.location.assign(checkout_url);
};

const handleUnauthenticatedRedirect = (
  navigate: (path: string) => void,
  billingPeriod: 'monthly' | 'yearly',
  tierLevel: number,
) => {
  const planParam = billingPeriod === 'yearly' ? '&plan=yearly' : '';

  navigate(`/signup?tier=${tierLevel}${planParam}`);
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
  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'yearly'>('monthly');
  const [successState, setSuccessState] = useState<{type: 'upgrade' | 'downgrade' | 'cancel' | 'resume', tierName: string} | null>(null);
  const [errorState, setErrorState] = useState<string | null>(null);
  
  const [pendingAction, setPendingAction] = useState<{
    tierLevel: number;
    tierIndex: number;
    actionType: 'upgrade' | 'downgrade' | 'resume' | 'subscribe';
    tierName: string;
  } | null>(null);
  const [previewData, setPreviewData] = useState<PreviewSubscriptionResponse | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  useEffect(() => {
    if (false) {
      setIsPreviewLoading(false);
    }
  }, []);

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
      setPreviewData(null);
    }
  }, [open, dispatch, tiers.length]);

  const handleSubscribe = async (tierLevel: number, tierIndex: number) => {
    if (!user) {
      handleUnauthenticatedRedirect(navigate, billingPeriod, tierLevel);

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
    const { tierLevel, tierIndex } = pendingAction;
    
    setPendingAction(null);
    setSubmittingTier(tierIndex);
    setErrorState(null);

    try {
      const tier = tiers.find((t) => t.level === tierLevel);

      if (!tier) {
        setSubmittingTier(null);

        return;
      }

      const priceId = getPriceId(tier, billingPeriod);

      if (!priceId) {
        setErrorState('This plan is not yet available for yearly billing.');
        setSubmittingTier(null);

        return;
      }

      await startCheckout(priceId);

    } catch (e: any) {
      console.error('Subscription error:', e);
      const msg = e.response?.data?.detail || 'Failed to process subscription. Please try again.';

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
              {user?.tier_level && user.tier_level > 1 ? 'Change Subscription' : 'Upgrade Subscription'}
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
                Please wait while we securely update your subscription. Do not close this window.
              </p>
            </div>
          </div>
        )}

        <DialogHeader className="mb-2">
          <DialogTitle className="text-2xl font-bold text-center">
            Upgrade Your Subscription
          </DialogTitle>
        </DialogHeader>
        
        <div className="flex flex-col items-center">
          <PricingSwitch
            billingPeriod={billingPeriod}
            setBillingPeriod={setBillingPeriod}
            className="mt-0"
          />

          <div className="w-full -mt-4">
            <PricingCards
              isLoading={isLoading}
              isFallback={isFallback}
              handleSubscribe={handleSubscribe}
              tiers={tiers}
              billingPeriod={billingPeriod}
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
              {successState?.type === 'downgrade' 
                ? 'Successfully scheduled the downgrade' 
                : `Successfully ${successState?.type === 'upgrade' ? 'Upgraded' : 'Resumed'}`}
            </AlertDialogTitle>
            <AlertDialogDescription className="text-base text-left text-muted-foreground mt-2">
              {successState?.type === 'downgrade' ? (
                <>Your downgrade to the <span className="font-bold text-primary">{successState?.tierName}</span> plan has been successfully scheduled.</>
              ) : successState?.type === 'resume' ? (
                <>Your <span className="font-bold text-primary">{successState?.tierName}</span> plan has been successfully resumed and all pending changes have been canceled.</>
              ) : (
                <>You are now on the <span className="font-bold text-primary">{successState?.tierName}</span> plan.</>
              )}
              
              <div className="bg-primary/5 border border-primary/20 p-4 rounded-xl text-sm text-left w-full mt-4 space-y-2">
                <h4 className="font-bold text-foreground">How billing works:</h4>
                {successState?.type === 'downgrade' ? (
                  <p className="text-muted-foreground leading-relaxed">
                    You will retain your current premium features until the end of your billing cycle. From the next billing period, your tier will be automatically updated and you will be billed for the new plan.
                  </p>
                ) : successState?.type === 'upgrade' ? (
                  <p className="text-muted-foreground leading-relaxed">
                    Your payment method has been securely charged the prorated difference for your new plan. Your billing cycle date remains the same.
                  </p>
                ) : successState?.type === 'resume' ? (
                  <p className="text-muted-foreground leading-relaxed">
                    Your current billing cycle will continue uninterrupted. Your plan will automatically renew on your next billing date.
                  </p>
                ) : (
                  <p className="text-muted-foreground leading-relaxed">
                    Your billing has been adjusted successfully.
                  </p>
                )}
              </div>
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
                `Are you sure you want to resume the ${pendingAction?.tierName} plan and cancel any pending changes?`
              ) : pendingAction?.actionType === 'downgrade' ? (
                `Are you sure you want to downgrade to the ${pendingAction?.tierName} plan? This change will take effect at the end of your current billing cycle.`
              ) : pendingAction?.actionType === 'subscribe' ? (
                `You are about to start a new subscription to the ${pendingAction?.tierName} plan.`
              ) : (
                `Are you sure you want to upgrade to the ${pendingAction?.tierName} plan?`
              )}

              {/* Preview Details */}
              {isPreviewLoading ? (
                <div className="mt-4 p-4 bg-muted/20 rounded-xl border border-border flex items-center justify-center">
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                </div>
              ) : previewData ? (
                <div className="mt-4 p-4 bg-primary/5 rounded-xl border border-primary/20 space-y-3">
                  <h4 className="font-semibold text-foreground border-b border-border/40 pb-2">Payment Breakdown</h4>
                  
                  {previewData.unused_credit_balance && previewData.unused_credit_balance > 0 ? (
                    <>
                      <div className="flex justify-between items-center text-sm">
                        <span className="text-muted-foreground">Cost of New Plan (This Cycle):</span>
                        <span className="font-medium text-foreground">
                          {previewData.credit_applied_today?.toFixed(2)} {previewData.currency}
                        </span>
                      </div>
                      <div className="flex justify-between items-center text-sm">
                        <span className="text-muted-foreground">Credit Applied Today:</span>
                        <span className="font-medium text-green-500">
                          -{previewData.credit_applied_today?.toFixed(2)} {previewData.currency}
                        </span>
                      </div>
                      <div className="flex justify-between items-center text-sm font-bold border-t border-border/40 pt-2 mt-2">
                        <span className="text-foreground">Amount Due Today:</span>
                        <span className="text-foreground">
                          {previewData.amount_due_today === 0 ? 'No Charge' : `${previewData.amount_due_today.toFixed(2)} ${previewData.currency}`}
                        </span>
                      </div>
                    </>
                  ) : (
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-muted-foreground">Amount Due Today:</span>
                      <span className="font-bold text-foreground">
                        {previewData.amount_due_today === 0 ? 'No Charge' : `${previewData.amount_due_today.toFixed(2)} ${previewData.currency}`}
                      </span>
                    </div>
                  )}
                  
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-muted-foreground">Next Billing Date:</span>
                    <span className="font-medium text-foreground">
                      {new Date(previewData.next_billing_date * 1000).toLocaleDateString()}
                    </span>
                  </div>

                  <div className="flex justify-between items-center text-sm">
                    <span className="text-muted-foreground">Next Cycle Total:</span>
                    <span className="font-bold text-primary">
                      {previewData.new_total.toFixed(2)} {previewData.currency}
                    </span>
                  </div>

                  {(previewData.unused_credit_balance ?? 0) > 0 && (
                    <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 mt-3 space-y-2">
                      <p className="text-xs text-blue-600 dark:text-blue-400 font-medium leading-relaxed">
                        You have a remaining credit balance of <strong>${previewData.unused_credit_balance!.toFixed(2)}</strong> from your previous plan. This has been added to your account and will automatically be used to pay for future billing cycles until it runs out.
                      </p>
                      {previewData.new_total > 0 && (
                        <p className="text-xs text-blue-600/80 dark:text-blue-400/80 italic border-t border-blue-500/20 pt-2">
                          Based on your new plan's cost of ${previewData.new_total}/cycle, this credit will fully cover your bills for the next {Math.floor(previewData.unused_credit_balance! / previewData.new_total)} cycles, keeping your amount due at $0 until approximately <strong>{new Date((previewData.next_billing_date + (Math.floor(previewData.unused_credit_balance! / previewData.new_total) * 30 * 24 * 60 * 60)) * 1000).toLocaleDateString(undefined, {month: 'long', year: 'numeric'})}</strong>.
                        </p>
                      )}
                    </div>
                  )}

                  {previewData.is_yearly_to_monthly && (
                    <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 mt-3">
                      <p className="text-xs text-yellow-600 dark:text-yellow-400 font-medium leading-relaxed">
                        <strong>Warning:</strong> You are switching from a Yearly plan to a Monthly plan. If your intention is to upgrade to the Yearly version of the {pendingAction?.tierName} plan, please click Cancel, toggle your billing period to "Yearly", and try upgrading again.
                      </p>
                    </div>
                  )}

                  {previewData.is_downgrade && (
                    <p className="text-xs text-muted-foreground mt-2 pt-2 border-t border-border/40 italic">
                      Your downgrade will be scheduled to take effect on the next billing date. You will retain current access until then.
                    </p>
                  )}
                </div>
              ) : null}

            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-6">
            <AlertDialogCancel className="rounded-xl h-12 px-6">Cancel</AlertDialogCancel>
            <AlertDialogAction 
              onClick={executeSubscribe} 
              disabled={isPreviewLoading}
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
