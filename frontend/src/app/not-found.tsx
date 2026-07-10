'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/** Catch-all: redirect any unknown route to home. */
export default function NotFound() {
  const router = useRouter();
  useEffect(() => { router.replace('/'); }, [router]);
  return null;
}
