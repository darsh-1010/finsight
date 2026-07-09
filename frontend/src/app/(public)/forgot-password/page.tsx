'use client';

import { Suspense } from 'react';
import ForgotPasswordPage from '@/views/ForgotPasswordPage';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <ForgotPasswordPage />
    </Suspense>
  );
}