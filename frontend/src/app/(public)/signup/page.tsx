'use client';

import { Suspense } from 'react';
import SignupPage from '@/views/SignupPage';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <SignupPage />
    </Suspense>
  );
}