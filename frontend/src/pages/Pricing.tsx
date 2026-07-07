import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import type { User } from '@/api/auth';
import { createCheckoutSession } from '@/api/payments';
import PricingAlternative from '@/components/pricing/PricingAlternative';
import PricingCards from '@/components/pricing/PricingCards';
import PricingCompare from '@/components/pricing/PricingCompare';
import PricingError from '@/components/pricing/PricingError';
import PricingHeader from '@/components/pricing/PricingHeader';
import PricingSwitch from '@/components/pricing/PricingSwitch';
import { useAuth } from '@/context/AuthContext';
import { useAlert } from '@/context/AlertContext';
import type { PricingTier } from '@/lib/interfaces/Pricing';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import {
  fetchTiers,
  selectTiers,
  selectTiersLoading,
  selectTiersError,
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
  navigate: ReturnType<typeof useNavigate>,
  billingPeriod: 'monthly' | 'yearly',
  tierLevel: number,
) => {
  const planParam = billingPeriod === 'yearly' ? '&plan=yearly' : '';

  navigate(`/signup?tier=${tierLevel}${planParam}`);
};

const handleSubscribeHelper = async ({
  user,
  tierLevel,
  tierIndex,
  tiers,
  billingPeriod,
  navigate,
  setSubmittingTier,
  showAlert,
}: {
  user: User | null;
  tierLevel: number;
  tierIndex: number;
  tiers: PricingTier[];
  billingPeriod: 'monthly' | 'yearly';
  navigate: ReturnType<typeof useNavigate>;
  setSubmittingTier: (val: number | null) => void;
  showAlert: (title: string, desc: string) => void;
}) => {
  if (!user) {
    handleUnauthenticatedRedirect(navigate, billingPeriod, tierLevel);

    return;
  }

  setSubmittingTier(tierIndex);

  await attemptSubscriptionProcess(
    tierLevel,
    tiers,
    (tier) => getPriceId(tier, billingPeriod),
    startCheckout,
    showAlert,
  );

  setSubmittingTier(null);
};

const usePricing = () => {
  const { user } = useAuth();
  const { showAlert } = useAlert();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();

  const [submittingTier, setSubmittingTier] = useState<number | null>(null);
  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'yearly'>(
    'monthly',
  );

  const tiers = useAppSelector(selectTiers);
  const isLoading = useAppSelector(selectTiersLoading);
  const error = useAppSelector(selectTiersError);
  const isFallback = useAppSelector(selectIsFallback);

  useEffect(() => {
    dispatch(fetchTiers());
  }, [dispatch]);

  const handleSubscribe = (tierLevel: number, tierIndex: number) => handleSubscribeHelper({
    user,
    tierLevel,
    tierIndex,
    tiers,
    billingPeriod,
    navigate,
    setSubmittingTier,
    showAlert,
  });

  return {
    submittingTier,
    setBillingPeriod,
    isLoading,
    error,
    isFallback,
    handleSubscribe,
    tiers,
    billingPeriod,
  };
};

const Pricing: React.FC = () => {
  const {
    submittingTier,
    setBillingPeriod,
    isLoading,
    error,
    isFallback,
    handleSubscribe,
    tiers,
    billingPeriod,
  } = usePricing();

  if (error && tiers.length === 0) {
    return <PricingError error={error} />;
  }

  return (
    <div className="flex items-center flex-col pt-20 pb-20 min-h-[calc(100vh-80px)] px-4 md:px-16 lg:px-32">
      {error && isFallback && (
        <div className="w-full max-w-2xl mb-8 p-4 glass-panel text-amber-500 border-amber-500/30 rounded-xl shadow-lg shadow-amber-500/5 text-sm text-center">
          {error}
        </div>
      )}

      <PricingHeader />
      <PricingSwitch
        billingPeriod={billingPeriod}
        setBillingPeriod={setBillingPeriod}
      />

      <PricingCards
        isLoading={isLoading}
        isFallback={isFallback}
        handleSubscribe={handleSubscribe}
        tiers={tiers}
        billingPeriod={billingPeriod}
        submittingTier={submittingTier}
      />

      <PricingCompare isLoading={isLoading} tiers={tiers} />

      <PricingAlternative />
    </div>
  );
};

const attemptSubscriptionProcess = async (
  tierLevel: number,
  tiers: PricingTier[],
  getPriceId: (tier: PricingTier) => string | null | undefined,
  startCheckout: (priceId: string) => Promise<void>,
  showAlert: (title: string, desc: string) => void,
) => {
  try {
    const tier = tiers.find((t) => t.level === tierLevel);

    if (!tier) return;

    const priceId = getPriceId(tier);

    if (!priceId) {
      showAlert('Plan Unavailable', 'This plan is not yet available for yearly billing.');

      return;
    }
    await startCheckout(priceId);
  } catch (e) {
    console.error('Checkout error:', e);
    showAlert('Checkout Error', 'Failed to start checkout. Please try again.');
  }
};

export default Pricing;
