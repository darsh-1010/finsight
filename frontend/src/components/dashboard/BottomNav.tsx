import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React from 'react';
import { 
  PiLayoutDuotone, 
  PiChatCircleTextDuotone, 
  PiChartLineUpDuotone 
} from 'react-icons/pi';

import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/utils';

const getNavItems = (isAdmin: boolean) => {
  const items = [
    {
      label: 'Dashboard',
      icon: <PiLayoutDuotone size={24} />,
      path: '/dashboard',
    },
    {
      label: 'Ask FinSight',
      icon: <PiChatCircleTextDuotone size={24} />,
      path: '/ask_finsight',
    },
    {
      label: 'Insights',
      icon: <PiChartLineUpDuotone size={24} />,
      path: '/market_insights',
    },
  ];

  if (isAdmin) {
    items.push({
      label: 'Admin',
      icon: <PiLayoutDuotone size={24} />,
      path: '/admin',
    });
  }

  return items;
};

const BottomNav: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const navItems = getNavItems(isAdmin);
  const pathname = usePathname();

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white dark:bg-[#08070A] border-t border-gray-200 dark:border-gray-800 z-50 px-2 py-3">
      <div className="flex items-center justify-around max-w-lg mx-auto">
        {navItems.map((item) => (
          <Link
            key={item.path}
            href={item.path}
            className={cn(
              'flex flex-col items-center gap-1 transition-colors',
              pathname === item.path
                ? 'text-primary scale-110'
                : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'
            )}
          >
            {item.icon}
            <span className="text-[10px] font-medium uppercase tracking-wider">
              {item.label}
            </span>
          </Link>
        ))}
      </div>
    </nav>
  );
};

export default BottomNav;
