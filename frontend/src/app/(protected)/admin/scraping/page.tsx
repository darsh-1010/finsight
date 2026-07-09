'use client';

import { Suspense } from 'react';
import AdminScrapingPage from '@/views/admin/AdminScrapingPage';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <AdminScrapingPage />
    </Suspense>
  );
}