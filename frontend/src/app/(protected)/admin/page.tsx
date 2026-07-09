'use client';

import { Suspense } from 'react';
import AdminDashboard from '@/views/admin/AdminDashboard';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <AdminDashboard />
    </Suspense>
  );
}