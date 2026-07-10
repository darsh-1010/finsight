'use client';

import { Suspense } from 'react';
import AskFinSight from '@/views/AskFinSight';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <AskFinSight />
    </Suspense>
  );
}