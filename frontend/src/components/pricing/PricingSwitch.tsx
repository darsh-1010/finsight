import React from 'react';

interface PricingSwitchProps {
  billingPeriod: 'monthly' | 'yearly';
  setBillingPeriod: React.Dispatch<React.SetStateAction<'monthly' | 'yearly'>>;
  className?: string;
}

const PricingSwitch: React.FC<PricingSwitchProps> = ({
  billingPeriod,
  setBillingPeriod,
  className = "mt-16",
}) => (
  <div className={`${className} flex items-center justify-center gap-4`}>
    <span
      className={`text-sm ${billingPeriod === 'monthly' ? 'font-semibold text-primary' : 'text-gray-500'}`}
    >
      Monthly
    </span>
    <button
      onClick={() => setBillingPeriod((prev) => (prev === 'monthly' ? 'yearly' : 'monthly'))
      }
      className="relative w-12 h-6 rounded-full bg-gray-200 dark:bg-gray-800 transition-colors focus:outline-none"
    >
      <div
        className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-primary transition-transform duration-200 ${billingPeriod === 'yearly' ? 'translate-x-6' : ''}`}
      />
    </button>
    <div className="flex items-center gap-2">
      <span
        className={`text-sm ${billingPeriod === 'yearly' ? 'font-semibold text-primary' : 'text-gray-500'}`}
      >
        Yearly
      </span>
      <span className="bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 text-[10px] px-2 py-0.5 rounded-full font-medium">
        Best Value
      </span>
    </div>
  </div>
);

export default PricingSwitch;
