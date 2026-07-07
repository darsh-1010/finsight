import React from 'react';
import { IoMdCheckmark } from 'react-icons/io';

import { Skeleton } from '@/components/ui/skeleton';
import type { PricingTier } from '@/lib/interfaces/Pricing';

const labelData = [
  {
    label: 'Education depth',
    values: [
      'Foundations',
      'Full curriculum',
      'Advanced',
      'Professional',
      'Elite',
    ],
  },
  {
    label: 'Intelligence level',
    values: [
      'Read-only',
      'Q&A mode',
      'Interactive AI',
      'Signals-aware',
      'Full access',
    ],
  },
  {
    label: 'AI interaction',
    values: [
      'Explain mode',
      'Education Q&A',
      'Full FinSight',
      'Priority compute',
      'Priority compute',
    ],
  },
  {
    label: 'Risk tools',
    values: ['-', 'Basic', 'Frameworks', 'Advanced', 'Advanced'],
  },
  {
    label: 'Signals awareness',
    values: ['-', '-', '-', '✓', '✓'],
  },
  {
    label: 'Community access',
    values: ['-', '-', '-', '-', '✓'],
  },
];

interface PricingCompareProps {
  isLoading: boolean;
  tiers: PricingTier[];
}

const TableBodyComponent: React.FC<PricingCompareProps> = ({
  isLoading,
  tiers,
}) => {
  const safeTiers = Array.isArray(tiers) ? tiers : [];
  
  return (
    <tbody>
      {labelData.map((row, i) => (
        <tr
          key={i}
          className="border-b border-gray-100 dark:border-gray-900 last:border-0 hover:bg-gray-50/50 dark:hover:bg-gray-800/20 transition-colors"
        >
          <td className="py-6 px-4 text-gray-600 dark:text-gray-400 font-medium">
            {row.label}
          </td>
          {isLoading
            ? Array.from({ length: 5 }).map((_, j) => (
              <td key={j} className="py-6 px-4">
                <Skeleton className="h-4 w-12 mx-auto" />
              </td>
            ))
            : row.values.slice(0, safeTiers.length).map((val, j) => (
              <td
                key={j}
                className="py-6 px-4 text-center text-sm md:text-base"
              >
                {val === '✓' ? (
                  <div className="flex justify-center text-primary">
                    <IoMdCheckmark size={18} />
                  </div>
                ) : (
                  val
                )}
              </td>
            ))}
        </tr>
      ))}
    </tbody>
  );
};

const PricingCompare: React.FC<PricingCompareProps> = ({ isLoading, tiers }) => {
  const safeTiers = Array.isArray(tiers) ? tiers : [];
  
  return (
    <div className="mt-32 w-full max-w-6xl">
      <h2 className="text-3xl font-medium text-center mb-16">
        Compare tiers at a glance
      </h2>
  
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-200 dark:border-gray-800">
              <th className="py-6 px-4 font-medium text-gray-500">Feature</th>
              {isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                  <th key={i} className="py-6 px-4">
                    <Skeleton className="h-6 w-20 mx-auto" />
                  </th>
                ))
                : safeTiers.map((tier) => (
                  <th
                    key={tier.level}
                    className="py-6 px-4 font-medium text-center"
                  >
                    {tier.name}
                  </th>
                ))}
            </tr>
          </thead>
          <TableBodyComponent isLoading={isLoading} tiers={safeTiers} />
        </table>
      </div>
    </div>
  );
};

export default PricingCompare;
