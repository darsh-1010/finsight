'use client';

import { Suspense } from 'react';

import Loader from '@/components/common/Loader';
import Research from '@/views/Research';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <Research />
    </Suspense>
  );
}
