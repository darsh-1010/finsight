'use client';

import { Suspense } from 'react';
import Product from '@/views/Product';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <Product />
    </Suspense>
  );
}