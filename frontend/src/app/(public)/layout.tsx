'use client';

import React from 'react';
import Navbar from '@/components/common/Navbar';
import Footer from '@/components/common/Footer';
import { useTheme } from '@/context/ThemeContext';

/**
 * Public layout — Navbar + Footer wrapper for all public-facing pages.
 * Replaces the old PublicLayout component (Outlet → children).
 */
export default function PublicGroupLayout({ children }: { children: React.ReactNode }) {
  const { theme } = useTheme();

  return (
    <div
      className={`min-h-screen flex flex-col ${
        theme === 'dark' ? 'bg-[#08070A] text-white' : 'bg-background text-foreground'
      }`}
    >
      <Navbar />
      <div className="pt-20 flex-1">
        <div className="page-transition">{children}</div>
      </div>
      <Footer />
    </div>
  );
}
