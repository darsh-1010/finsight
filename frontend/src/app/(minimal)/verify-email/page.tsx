'use client';

import { Suspense } from 'react';

import Loader from '@/components/common/Loader';
import VerifyEmailPage from '@/views/VerifyEmailPage';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <VerifyEmailPage />
    </Suspense>
  );
}