'use client';

import { Suspense } from 'react';
import Pricing from '@/views/Pricing';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <Pricing />
    </Suspense>
  );
}