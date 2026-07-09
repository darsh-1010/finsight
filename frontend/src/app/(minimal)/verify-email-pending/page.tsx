'use client';

import { Suspense } from 'react';
import EmailVerificationNotice from '@/views/EmailVerificationNotice';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <EmailVerificationNotice />
    </Suspense>
  );
}