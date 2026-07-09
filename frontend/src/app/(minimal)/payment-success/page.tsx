'use client';

import { Suspense } from 'react';
import PaymentSuccess from '@/views/PaymentSuccess';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <PaymentSuccess />
    </Suspense>
  );
}