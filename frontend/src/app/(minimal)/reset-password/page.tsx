'use client';

import { Suspense } from 'react';

import Loader from '@/components/common/Loader';
import ResetPasswordPage from '@/views/ResetPasswordPage';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <ResetPasswordPage />
    </Suspense>
  );
}