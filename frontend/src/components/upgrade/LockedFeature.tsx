import { Lock } from 'lucide-react';
import React from 'react';
import { useNavigate } from 'react-router-dom';

import { PROFILE_SUBSCRIPTION_PATH } from '@/lib/profileRoutes';

import { Button } from '../ui/button';


interface LockedFeatureProps {
  title: string;
  description: string;
  requiredTier: number;
}

const LockedFeature: React.FC<LockedFeatureProps> = ({
  title,
  description,
  requiredTier,
}) => {
  const navigate = useNavigate();

  return (
    <div className="border border-dashed border-gray-300 dark:border-gray-700 rounded-2xl p-6 text-center bg-gray-50 dark:bg-[#0B0A10]">
      <div className="flex justify-center mb-3">
        <div className="p-3 rounded-full bg-gray-200 dark:bg-gray-800">
          <Lock className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        </div>
      </div>

      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
        {description}
      </p>

      <p className="mt-4 text-sm font-medium">
        🔒 Unlocks at <span className="text-blue-600">Tier {requiredTier}</span>
      </p>

      <Button className="mt-4" size="sm" onClick={() => navigate(PROFILE_SUBSCRIPTION_PATH)}>
        Upgrade Plan
      </Button>
    </div>
  );
};

export default LockedFeature;
