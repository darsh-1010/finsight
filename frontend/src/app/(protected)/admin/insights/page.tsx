'use client';

import { Suspense } from 'react';
import AdminInsightsPage from '@/views/admin/AdminInsightsPage';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <AdminInsightsPage />
    </Suspense>
  );
}