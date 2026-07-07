import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';

import Navbar from '../components/common/Navbar';
import { useTheme } from '../context/ThemeContext';

import Footer from '@/components/common/Footer';

const PublicLayout: React.FC = () => {
  const { theme } = useTheme();
  const location = useLocation();

  return (
    <div
      className={`min-h-screen flex flex-col ${theme === 'dark' ? 'bg-[#08070A] text-white' : 'bg-background text-foreground'}`}
    >
      <Navbar />
      <div className="pt-20 flex-1">
        <div key={location.pathname} className="page-transition">
          <Outlet />
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default PublicLayout;
