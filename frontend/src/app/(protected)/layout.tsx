'use client';

import React, { useState } from 'react';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Loader from '@/components/common/Loader';
import Sidebar from '@/components/dashboard/Sidebar';
import DashboardHeader from '@/components/dashboard/DashboardHeader';
import BottomNav from '@/components/dashboard/BottomNav';
import { cn } from '@/lib/utils';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/market_insights': 'Market Insights',
  '/ask_finsight': 'Ask FinSight',
  '/user_profile': 'User Profile',
  '/onboarding': 'Onboarding',
  '/research': 'Research',
  '/admin': 'Admin Dashboard',
  '/admin/users': 'Users Management',
  '/admin/chatbot': 'Chatbot Management',
  '/admin/scraping': 'Scraping Management',
  '/admin/insights': 'Insights Review',
};

/**
 * Protected route group layout — Sidebar + DashboardHeader + BottomNav.
 * Guards against unauthenticated access. Replaces ProtectedRouteLayout + ProtectedRoute.
 */
export default function ProtectedGroupLayout({ children }: { children: React.ReactNode }) {
  const { isLoggedIn, isLoading } = useAuth();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  if (isLoading) return <Loader />;
  if (!isLoggedIn) {
    if (typeof window !== 'undefined') window.location.replace('/login');
    return <Loader />;
  }

  const title = PAGE_TITLES[pathname] ?? 'Dashboard';

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#08070A] transition-colors duration-300">
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
      <div
        className={cn(
          'transition-all duration-300 min-h-screen flex flex-col',
          collapsed ? 'md:pl-20' : 'md:pl-64',
          'pb-20 md:pb-0',
        )}
      >
        <DashboardHeader collapsed={collapsed} title={title} />
        <main className="flex-1 pt-16 w-full">
          <div className="page-transition">{children}</div>
        </main>
        <BottomNav />
      </div>
    </div>
  );
}
