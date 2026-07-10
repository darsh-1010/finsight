'use client';

import { useEffect, Suspense } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Loader from '@/components/common/Loader';
import UserOnboarding from '@/views/UserOnboarding';

function OnboardingContent() {
  const { isLoggedIn, isLoading, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!isLoggedIn) { router.replace('/login'); return; }
    if (user?.is_onboarded) { router.replace('/dashboard'); }
  }, [isLoggedIn, isLoading, user, router]);

  if (isLoading || !isLoggedIn) return <Loader />;
  return <UserOnboarding />;
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={<Loader />}>
      <OnboardingContent />
    </Suspense>
  );
}