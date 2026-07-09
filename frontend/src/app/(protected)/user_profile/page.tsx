'use client';

import { Suspense } from 'react';
import UserProfile from '@/views/UserProfile';
import Loader from '@/components/common/Loader';

export default function Page() {
  return (
    <Suspense fallback={<Loader />}>
      <UserProfile />
    </Suspense>
  );
}