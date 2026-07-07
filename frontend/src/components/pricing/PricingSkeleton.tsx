import React from 'react';

import { Skeleton } from '@/components/ui/skeleton';

const PricingSkeleton: React.FC = () => (
  <div className="border border-gray-200 p-4 rounded-lg bg-white dark:bg-[#08070A] dark:border-gray-800 flex flex-col">
    <Skeleton className="w-10 h-10 rounded-lg mb-4" />
    <Skeleton className="h-6 w-3/4 mb-4" />
    <Skeleton className="h-8 w-1/2 mb-6" />
    <hr className="my-4" />
    <div className="grow">
      <Skeleton className="h-4 w-full mb-2" />
      <Skeleton className="h-4 w-5/6 mb-6" />
      <div className="space-y-2 mb-6">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
      </div>
    </div>
    <Skeleton className="h-10 w-full mt-4" />
  </div>
);

export default PricingSkeleton;
