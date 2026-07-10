'use client';

import { Suspense } from 'react';
import Dashboard from '@/views/Dashboard';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <Dashboard />
    </Suspense>
  );
}