'use client';

import { Suspense } from 'react';
import MarketInsigts from '@/views/MarketInsigts';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <MarketInsigts />
    </Suspense>
  );
}