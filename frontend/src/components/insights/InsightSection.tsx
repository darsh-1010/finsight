import React from 'react';

import Can from '@/components/auth/Can';
import LockedFeature from '@/components/upgrade/LockedFeature';

interface InsightSectionProps {
  entitlement: string;
  minTier: number;
  title: string;
  description: string;
  children: React.ReactNode;
}

const InsightSection: React.FC<InsightSectionProps> = ({
  entitlement,
  minTier,
  title,
  description,
  children,
}) => (
  <Can
    entitlement={entitlement}
    fallback={
      <LockedFeature
        title={title}
        description={description}
        requiredTier={minTier}
      />
    }
  >
    <div className="border rounded-2xl p-6 bg-white dark:bg-[#08070A]">
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      {children}
    </div>
  </Can>
);

export default InsightSection;
