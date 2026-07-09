'use client';

import { Suspense } from 'react';
import AboutUs from '@/views/AboutUs';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <AboutUs />
    </Suspense>
  );
}