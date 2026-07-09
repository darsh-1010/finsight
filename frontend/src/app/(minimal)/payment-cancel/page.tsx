'use client';

import { Suspense } from 'react';
import PaymentCancel from '@/views/PaymentCancel';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <PaymentCancel />
    </Suspense>
  );
}