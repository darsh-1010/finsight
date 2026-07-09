'use client';

import { Suspense } from 'react';
import VerifyEmailPage from '@/views/VerifyEmailPage';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <VerifyEmailPage />
    </Suspense>
  );
}