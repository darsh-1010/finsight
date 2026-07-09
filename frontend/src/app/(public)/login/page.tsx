'use client';

import { Suspense } from 'react';
import LoginPage from '@/views/LoginPage';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <LoginPage />
    </Suspense>
  );
}