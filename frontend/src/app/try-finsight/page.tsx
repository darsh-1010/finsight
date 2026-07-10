'use client';

import { Suspense } from 'react';
import TryAskFinSight from '@/views/TryAskFinSight';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <TryAskFinSight />
    </Suspense>
  );
}