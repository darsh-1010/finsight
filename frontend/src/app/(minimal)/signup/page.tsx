'use client';

import { Suspense } from 'react';

import Loader from '@/components/common/Loader';
import SignupPage from '@/views/SignupPage';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <SignupPage />
    </Suspense>
  );
}