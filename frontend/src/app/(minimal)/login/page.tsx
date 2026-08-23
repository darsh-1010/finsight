'use client';

import { Suspense } from 'react';

import Loader from '@/components/common/Loader';
import LoginPage from '@/views/LoginPage';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <LoginPage />
    </Suspense>
  );
}