'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import LandingPage from '@/views/LandingPage';
import Loader from '@/components/common/Loader';

/**
 * Home route — shows LandingPage for guests, redirects logged-in users.
 */
export default function HomePage() {
  const { isLoggedIn, isLoading, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (isLoggedIn) {
      router.replace(user?.is_onboarded ? '/dashboard' : '/onboarding');
    }
  }, [isLoggedIn, isLoading, user, router]);

  if (isLoading || isLoggedIn) return <Loader />;
  return <LandingPage />;
}
