import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';

import BottomNav from '../components/dashboard/BottomNav';
import DashboardHeader from '../components/dashboard/DashboardHeader';
import Sidebar from '../components/dashboard/Sidebar';

import { cn } from '@/lib/utils';

const getPageTitle = (pathname: string) => {
  switch (pathname) {
  case '/dashboard':
    return 'Dashboard';
  case '/market_insights':
    return 'Market Insights';
  case '/ask_finsight':
    return 'Ask FinSight';
  case '/user_profile':
    return 'User Profile';
  case '/onboarding':
    return 'Onboarding';
  case '/payment-success':
    return 'Payment Success';
  case '/payment-cancel':
    return 'Payment Check';
  case '/admin':
    return 'Admin Dashboard';
  case '/admin/users':
    return 'Users Management';
  case '/admin/chatbot':
    return 'Chatbot Management';
  case '/admin/scraping':
    return 'Scraping Management';
  case '/admin/insights':
    return 'Insights Review';
  case '/admin/marketing':
    return 'Marketing Insights Management';
  case '/admin/signals':
    return 'Signal Management';
  default:
    return 'Dashboard';
  }
};

const ProtectedRouteLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#08070A] transition-colors duration-300">
      {/* Sidebar - Desktop */}
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />

      {/* Main Content Area */}
      <div
        className={cn(
          'transition-all duration-300 min-h-screen flex flex-col',
          collapsed ? 'md:pl-20' : 'md:pl-64',
          'pb-20 md:pb-0' // Add padding for bottom nav on mobile
        )}
      >
        {/* Header */}
        <DashboardHeader collapsed={collapsed} title={getPageTitle(location.pathname)} />

        {/* Page Content */}
        <main className="flex-1 pt-16 w-full">
          <div key={location.pathname} className="page-transition">
            <Outlet context={{ mainSidebarCollapsed: collapsed }} />
          </div>
        </main>

        {/* Bottom Navigation - Mobile only */}
        <BottomNav />
      </div>
    </div>
  );
};

export default ProtectedRouteLayout;
