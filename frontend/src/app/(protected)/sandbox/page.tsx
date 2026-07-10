'use client';

import { Suspense } from 'react';
import Sandbox from '@/views/Sandbox';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <Sandbox />
    </Suspense>
  );
}