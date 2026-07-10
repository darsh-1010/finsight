'use client';

import { Suspense } from 'react';
import AdminBrokersPage from '@/views/admin/AdminBrokersPage';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <AdminBrokersPage />
    </Suspense>
  );
}