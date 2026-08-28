'use client';

import { Suspense } from 'react';

import Loader from '@/components/common/Loader';
import ForgotPasswordPage from '@/views/ForgotPasswordPage';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <ForgotPasswordPage />
    </Suspense>
  );
}