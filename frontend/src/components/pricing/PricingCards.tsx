import React from 'react';
import { PiSealCheckFill } from 'react-icons/pi';

import PricingSkeleton from './PricingSkeleton';

import { Button } from '@/components/ui/button';
import type { PricingTier } from '@/lib/interfaces/Pricing';
import { getTierIcon } from '@/lib/utils';

interface PricingCardsProps {
  isLoading: boolean;
  tiers: PricingTier[];
  billingPeriod: 'monthly' | 'yearly';
  isFallback: boolean;
  handleSubscribe: (tierLevel: number, tierIndex: number) => Promise<void>;
  submittingTier: number | null;
  currentTierLevel?: number;
}

type TierIconType = React.ComponentType<{ size?: number }>;

const ICON_MAP: Record<number, TierIconType> = {
  1: getTierIcon(1),
  2: getTierIcon(2),
  3: getTierIcon(3),
  4: getTierIcon(4),
  5: getTierIcon(5),
};

const getPrice = (elm: PricingTier, billingPeriod: 'monthly' | 'yearly') => {
  if (billingPeriod === 'monthly') {
    return Number(elm.price_amount) / 100;
  }

  return (
    Math.round(Number(elm.price_amount_yearly) / 100) ||
    Math.round((Number(elm.price_amount) * 12 * 0.9) / 100)
  );
};

const TierHeader = ({
  Icon,
  isPopular,
  isCurrentPlan,
}: {
  Icon: React.ComponentType<{ size?: number }>;
  isPopular: boolean | undefined;
  isCurrentPlan: boolean;
}) => (
  <div className="flex justify-between items-start mb-2">
    <div
      className={`${
        isCurrentPlan || isPopular ? 'bg-background shadow-sm' : 'bg-secondary/50'
      } ${isCurrentPlan ? 'text-primary' : ''} p-3 rounded-xl`}
    >
      <Icon size={24} />
    </div>

    {isCurrentPlan ? (
      <div className="px-3 py-1 text-xs font-bold bg-primary text-primary-foreground rounded-full shadow-md">
        Current Plan
      </div>
    ) : isPopular && (
      <div className="px-3 py-1 text-xs font-medium bg-primary/10 text-primary rounded-full border border-primary/20">
        Most popular
      </div>
    )}
  </div>
);

const TierBody = ({
  elm,
  billingPeriod,
  price,
}: {
  elm: PricingTier;
  billingPeriod: 'monthly' | 'yearly';
  price: number;
}) => (
  <>
    <h3 className="text-3xl mt-4 min-h-12 font-bold text-foreground">
      {elm.name}
    </h3>

    <h5 className="text-2xl mt-2 font-bold">
      &#36;<span className="text-3xl">{price}</span>
      <span className="text-sm text-muted-foreground font-normal">
        {billingPeriod === 'monthly' ? ' / month' : ' / year'}
      </span>
    </h5>

    <hr className="my-4 border-border/60" />

    <p className="text-sm text-muted-foreground min-h-12 leading-relaxed">{elm.description}</p>

    <div className="mt-4 grow space-y-3">
      {elm.highlights.map((highlight, j) => (
        <div key={j} className="flex gap-3 items-start">
          <div className="mt-0.5">
            <PiSealCheckFill size={18} className="text-primary" />
          </div>
          <p className="text-sm font-medium leading-tight">{highlight}</p>
        </div>
      ))}
    </div>
  </>
);

const TierFooter = ({
  isFallback,
  submittingTier,
  index,
  elm,
  handleSubscribe,
  currentTierLevel,
  isCancelingAtPeriodEnd,
  scheduledTierLevel,
}: {
  isFallback: boolean;
  submittingTier: number | null;
  index: number;
  elm: PricingTier;
  handleSubscribe: (tierLevel: number, tierIndex: number) => Promise<void>;
  currentTierLevel?: number;
  isCancelingAtPeriodEnd?: boolean;
  scheduledTierLevel?: number | null;
}) => {
  let buttonText = 'Get Started Now';
  let isDisabled = isFallback;
  let variant: 'default' | 'outline' | 'secondary' = 'default';

  if (currentTierLevel !== undefined) {
    if (elm.level === currentTierLevel) {
      if (isCancelingAtPeriodEnd || (scheduledTierLevel !== undefined && scheduledTierLevel !== null)) {
        buttonText = 'Resume Subscription';
        variant = 'outline';
        isDisabled = isFallback;
      } else {
        buttonText = 'Current Plan';
        isDisabled = true;
        variant = 'secondary';
      }
    } else if (elm.level > currentTierLevel) {
      buttonText = 'Upgrade';
      variant = 'default';
    } else {
      buttonText = 'Downgrade';
      variant = 'outline';
    }
  }

  // Override for scheduled downgrade
  if (scheduledTierLevel !== undefined && scheduledTierLevel === elm.level) {
    buttonText = 'Downgrade Scheduled';
    isDisabled = true;
    variant = 'secondary';
  }

  if (submittingTier === index) {
    buttonText = 'Loading...';
  }

  return (
    <Button
      variant={variant}
      className={`w-full mt-6 h-12 rounded-xl font-bold transition-all ${
        isDisabled && variant !== 'secondary' ? 'opacity-50 cursor-not-allowed' : ''
      } ${
        variant === 'default' 
          ? 'shadow-md shadow-primary/20 hover:shadow-lg hover:-translate-y-0.5' 
          : variant === 'outline'
          ? 'hover:bg-primary/5 hover:text-primary'
          : ''
      }`}
      disabled={isDisabled || submittingTier === index}
      onClick={() => {
        if (isDisabled) return;
        handleSubscribe(elm.level, index);
      }}
      title={isFallback ? 'try again after some time' : ''}
    >
      {buttonText}
    </Button>
  );
};

const TierCard = ({
  elm,
  index,
  billingPeriod,
  isFallback,
  handleSubscribe,
  submittingTier,
  currentTierLevel,
  isCancelingAtPeriodEnd,
  scheduledTierLevel,
}: {
  elm: PricingTier;
  index: number;
  billingPeriod: 'monthly' | 'yearly';
  isFallback: boolean;
  handleSubscribe: (tierLevel: number, tierIndex: number) => Promise<void>;
  submittingTier: number | null;
  currentTierLevel?: number;
  isCancelingAtPeriodEnd?: boolean;
  scheduledTierLevel?: number | null;
}) => {
  const Icon = ICON_MAP[elm.level];
  const price = getPrice(elm, billingPeriod);
  
  const isCurrentPlan = currentTierLevel !== undefined && elm.level === currentTierLevel;
  const currentPlanClasses = 'bg-background scale-[1.02] z-10 before:absolute before:-inset-[2px] before:bg-gradient-to-r before:from-primary before:to-purple-500 before:rounded-[1.6rem] before:z-[-1] before:opacity-100 shadow-2xl shadow-primary/20';
  const popularClasses = 'bg-background scale-[1.02] z-10 before:absolute before:-inset-[2px] before:bg-gradient-to-r before:from-accent before:to-purple-500 before:rounded-[1.6rem] before:z-[-1] before:opacity-100 shadow-xl shadow-accent/20';
  const normalClasses = 'glass-card hover:border-primary/30 shadow-sm hover:shadow-md hover:scale-[1.01]';

  return (
    <div
      className={`p-6 rounded-[1.5rem] relative overflow-hidden transition-all duration-300 flex flex-col ${
        isCurrentPlan ? currentPlanClasses : elm.is_popular ? popularClasses : normalClasses
      }`}
    >
      <TierHeader Icon={Icon} isPopular={elm.is_popular} isCurrentPlan={isCurrentPlan} />

      <TierBody elm={elm} billingPeriod={billingPeriod} price={price} />

      <TierFooter
        isFallback={isFallback}
        submittingTier={submittingTier}
        index={index}
        elm={elm}
        handleSubscribe={handleSubscribe}
        currentTierLevel={currentTierLevel}
        isCancelingAtPeriodEnd={isCancelingAtPeriodEnd}
        scheduledTierLevel={scheduledTierLevel}
      />
    </div>
  );
};

const PricingCards: React.FC<PricingCardsProps & { isCancelingAtPeriodEnd?: boolean; scheduledTierLevel?: number | null }> = ({
  isLoading,
  tiers,
  billingPeriod,
  isFallback,
  handleSubscribe,
  submittingTier,
  currentTierLevel,
  isCancelingAtPeriodEnd,
  scheduledTierLevel,
}) => {
  if (isLoading) {
    return (
      <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6 w-full max-w-8xl">
        {Array.from({ length: 5 }).map((_, i) => (
          <PricingSkeleton key={i} />
        ))}
      </div>
    );
  }

  return (
    <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6 w-full max-w-8xl">
      {(Array.isArray(tiers) ? tiers : []).map((elm, i) => (
        <TierCard
          key={i}
          elm={elm}
          index={i}
          billingPeriod={billingPeriod}
          isFallback={isFallback}
          handleSubscribe={handleSubscribe}
          submittingTier={submittingTier}
          currentTierLevel={currentTierLevel}
          isCancelingAtPeriodEnd={isCancelingAtPeriodEnd}
          scheduledTierLevel={scheduledTierLevel}
        />
      ))}
    </div>
  );
};

export default PricingCards;
