import { useRouter } from 'next/navigation';
import React, { useState, useEffect } from 'react';

import type { User } from '@/api/auth';
import { selectTier } from '@/api/payments';
import PricingAlternative from '@/components/pricing/PricingAlternative';
import PricingCards from '@/components/pricing/PricingCards';
import PricingCompare from '@/components/pricing/PricingCompare';
import PricingError from '@/components/pricing/PricingError';
import PricingHeader from '@/components/pricing/PricingHeader';
import { useAlert } from '@/context/AlertContext';
import { useAuth } from '@/context/AuthContext';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import {
  fetchTiers,
  selectTiers,
  selectTiersLoading,
  selectTiersError,
  selectIsFallback,
} from '@/store/slices/tierSlice';

const handleUnauthenticatedRedirect = (
  navigate: (path: string) => void,
  tierLevel: number,
) => {
  navigate(`/signup?tier=${tierLevel}`);
};

const attemptTierSwitch = async (
  tierLevel: number,
  showAlert: (title: string, desc: string) => void,
): Promise<boolean> => {
  try {
    await selectTier(tierLevel);

    return true;
  } catch (e) {
    console.error('Tier switch error:', e);
    showAlert('Something Went Wrong', 'Failed to switch plans. Please try again.');

    return false;
  }
};

const handleSubscribeHelper = async ({
  user,
  tierLevel,
  tierIndex,
  navigate,
  setSubmittingTier,
  showAlert,
}: {
  user: User | null;
  tierLevel: number;
  tierIndex: number;
  navigate: (path: string) => void;
  setSubmittingTier: (val: number | null) => void;
  showAlert: (title: string, desc: string) => void;
}) => {
  if (!user) {
    handleUnauthenticatedRedirect(navigate, tierLevel);

    return;
  }

  setSubmittingTier(tierIndex);
  const succeeded = await attemptTierSwitch(tierLevel, showAlert);

  setSubmittingTier(null);
  if (succeeded) {
    window.location.reload();
  }
};

const usePricing = () => {
  const { user } = useAuth();
  const { showAlert } = useAlert();
  const navigate = useRouter().push;
  const dispatch = useAppDispatch();

  const [submittingTier, setSubmittingTier] = useState<number | null>(null);

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
    navigate,
    setSubmittingTier,
    showAlert,
  });

  return {
    submittingTier,
    isLoading,
    error,
    isFallback,
    handleSubscribe,
    tiers,
  };
};

const Pricing: React.FC = () => {
  const {
    submittingTier,
    isLoading,
    error,
    isFallback,
    handleSubscribe,
    tiers,
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

      <PricingCards
        isLoading={isLoading}
        isFallback={isFallback}
        handleSubscribe={handleSubscribe}
        tiers={tiers}
        submittingTier={submittingTier}
      />

      <PricingCompare isLoading={isLoading} tiers={tiers} />

      <PricingAlternative />
    </div>
  );
};

export default Pricing;
