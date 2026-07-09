'use client';

import { Suspense } from 'react';
import ResetPasswordPage from '@/views/ResetPasswordPage';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <ResetPasswordPage />
    </Suspense>
  );
}