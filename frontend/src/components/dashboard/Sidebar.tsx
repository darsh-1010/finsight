import {
  ShieldCheck,
  Globe,
  ChevronDown,
  ChevronRight,
  Briefcase,
  Newspaper,
} from 'lucide-react';
import React, { useState } from 'react';
import {
  PiLayoutDuotone,
  PiChartLineUpDuotone,
  PiCaretLeftBold,
  PiCaretRightBold,
  PiChatCircleTextDuotone,
} from 'react-icons/pi';
import { Link, useLocation } from 'react-router-dom';

import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/utils';

interface SidebarProps {
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
  mobileOpen?: boolean;
  adminOnly?: boolean;
}
interface SidebarNavItemProps {
  item: {
    label: string;
    icon: React.ReactNode;
    path: string;
  };
  isActive: boolean;
  collapsed: boolean;
}
interface AdminSidebarSectionProps {
  collapsed: boolean;
  adminOpen: boolean;
  setAdminOpen: (open: boolean) => void;
  isAdminPath: boolean;
  location: ReturnType<typeof useLocation>;
}

const navItems = [
  {
    label: 'Dashboard',
    icon: <PiLayoutDuotone size={22} />,
    path: '/dashboard',
  },
  {
    label: 'Ask FinSight',
    icon: <PiChatCircleTextDuotone size={22} />,
    path: '/ask_finsight',
  },
  {
    label: 'Market Insights',
    icon: <PiChartLineUpDuotone size={22} />,
    path: '/market_insights',
  },
  {
    label: 'Portfolio Sandbox',
    icon: <Briefcase size={22} />,
    path: '/sandbox',
  },
];

const adminSubItems = [
  {
    label: 'Admin Dashboard',
    icon: <PiLayoutDuotone size={16} />,
    path: '/admin',
  },
  {
    label: 'Scraping Management',
    icon: <Globe size={16} />,
    path: '/admin/scraping',
  },
  {
    label: 'Insights Review',
    icon: <Newspaper size={16} />,
    path: '/admin/insights',
  },
];

// Sub-components
const SidebarHeader: React.FC<{ collapsed: boolean }> = ({ collapsed }) => (
  <div className="h-20 flex items-center px-6 mb-4 justify-center md:justify-start">
    <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
      {collapsed ? (
        <span className="font-extrabold text-2xl tracking-tight font-logo text-primary">FS</span>
      ) : (
        <span className="font-extrabold text-2xl tracking-tight font-logo bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">FinSight</span>
      )}
    </Link>
  </div>
);

const SidebarNavItem: React.FC<SidebarNavItemProps> = ({
  item,
  isActive,
  collapsed,
}) => (
  <Link
    to={item.path}
    className={cn(
      'flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group relative cursor-pointer font-medium text-sm',
      isActive
        ? 'bg-primary text-primary-foreground shadow-md shadow-primary/20'
        : 'text-gray-500 hover:bg-primary/10 hover:text-primary dark:text-gray-400 dark:hover:bg-primary/20 dark:hover:text-primary',
    )}
  >
    <div
      className={cn(
        isActive
          ? 'text-primary-foreground'
          : 'text-gray-400 group-hover:text-primary dark:group-hover:text-primary',
      )}
    >
      {item.icon}
    </div>
    {!collapsed && (
      <span className="font-medium text-sm whitespace-nowrap overflow-hidden transition-all duration-300">
        {item.label}
      </span>
    )}

    {/* Tooltip for collapsed state */}
    {collapsed && (
      <div className="absolute left-16 bg-gray-900 text-white px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 shadow-lg">
        {item.label}
      </div>
    )}
  </Link>
);

const AdminSubMenu: React.FC<{
  adminOpen: boolean;
  collapsed: boolean;
  location: ReturnType<typeof useLocation>;
}> = ({ adminOpen, collapsed, location }) => {
  if (!adminOpen && !collapsed) return null;

  return (
    <div className={cn('space-y-0.5', !collapsed && 'ml-3 md:mt-1 mt-4')}>
      {adminSubItems.map((sub) => {
        const isSubActive = location.pathname === sub.path;

        return (
          <Link
            key={sub.path}
            to={sub.path}
            className={cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 group relative',
              isSubActive
                ? 'bg-primary text-primary-foreground shadow-sm shadow-primary/20'
                : 'text-gray-500 hover:bg-primary/10 hover:text-primary dark:text-gray-400 dark:hover:bg-primary/20 dark:hover:text-primary',
            )}
          >
            <div
              className={cn(
                'shrink-0',
                isSubActive
                  ? 'text-primary-foreground'
                  : 'text-gray-400 group-hover:text-primary dark:group-hover:text-primary',
              )}
            >
              {sub.icon}
            </div>
            {!collapsed && (
              <span className="text-xs font-medium whitespace-nowrap">
                {sub.label}
              </span>
            )}
            {collapsed && (
              <div className="absolute left-16 bg-gray-900 text-white px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 shadow-lg">
                {sub.label}
              </div>
            )}
          </Link>
        );
      })}
    </div>
  );
};

const AdminToggleButton: React.FC<{
  adminOpen: boolean;
  collapsed: boolean;
  setAdminOpen: (v: boolean) => void;
  isAdminPath: boolean;
}> = ({ adminOpen, collapsed, setAdminOpen, isAdminPath }) => (
  <button
    onClick={() => !collapsed && setAdminOpen(!adminOpen)}
    className={cn(
      'w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-all duration-200 group relative',
      isAdminPath
        ? 'bg-primary text-primary-foreground shadow-md shadow-primary/20'
        : 'text-gray-500 hover:bg-primary/10 hover:text-primary dark:text-gray-400 dark:hover:bg-primary/20 dark:hover:text-primary',
    )}
  >
    <div
      className={cn(
        isAdminPath
          ? 'text-primary-foreground'
          : 'text-gray-400 group-hover:text-primary dark:group-hover:text-primary',
      )}
    >
      <ShieldCheck size={22} />
    </div>
    {!collapsed && (
      <>
        <span className="flex-1 font-medium text-sm text-left">
          Admin Panel
        </span>
        {adminOpen ? (
          <ChevronDown size={14} className="shrink-0" />
        ) : (
          <ChevronRight size={14} className="shrink-0" />
        )}
      </>
    )}
    {collapsed && (
      <div className="absolute left-16 bg-gray-900 text-white px-2 py-1 rounded text-xs opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50 shadow-lg">
        Admin Panel
      </div>
    )}
  </button>
);

const AdminSidebarSection: React.FC<AdminSidebarSectionProps> = ({
  collapsed,
  adminOpen,
  setAdminOpen,
  isAdminPath,
  location,
}) => (
  <div className="pt-12">
    {!collapsed && (
      <p className="px-3 pb-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        Admin
      </p>
    )}

    <AdminToggleButton
      adminOpen={adminOpen}
      collapsed={collapsed}
      setAdminOpen={setAdminOpen}
      isAdminPath={isAdminPath}
    />

    <AdminSubMenu
      adminOpen={adminOpen}
      collapsed={collapsed}
      location={location}
    />
  </div>
);

const SidebarCollapseButton: React.FC<{
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
}> = ({ collapsed, setCollapsed }) => (
  <div className="p-4 border-t border-gray-100 dark:border-gray-800">
    <button
      onClick={() => setCollapsed(!collapsed)}
      className="flex items-center justify-center w-full py-2 bg-gray-50 dark:bg-gray-900 rounded-lg text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors"
    >
      {collapsed ? <PiCaretRightBold /> : <PiCaretLeftBold />}
    </button>
  </div>
);

const SidebarContent: React.FC<{
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  mobileOpen?: boolean;
  location: ReturnType<typeof useLocation>;
  isAdmin: boolean;
  adminOpen: boolean;
  setAdminOpen: (v: boolean) => void;
  isAdminPath: boolean;
  adminOnly?: boolean;
}> = ({
  collapsed,
  setCollapsed,
  mobileOpen,
  location,
  isAdmin,
  adminOpen,
  setAdminOpen,
  isAdminPath,
  adminOnly,
}) => (
  <div className="flex flex-col h-full">
    {!adminOnly && <SidebarHeader collapsed={collapsed} />}

    <nav className="flex-1 px-3 space-y-1">
      {!adminOnly &&
        navItems.map((item) => (
          <SidebarNavItem
            key={item.path}
            item={item}
            isActive={location.pathname === item.path}
            collapsed={collapsed}
          />
        ))}

      {(isAdmin || adminOnly) && (
        <AdminSidebarSection
          collapsed={collapsed}
          adminOpen={adminOnly ? true : adminOpen}
          setAdminOpen={setAdminOpen}
          isAdminPath={isAdminPath}
          location={location}
        />
      )}
    </nav>

    {!mobileOpen && !adminOnly && (
      <SidebarCollapseButton
        collapsed={collapsed}
        setCollapsed={setCollapsed}
      />
    )}
  </div>
);

/* -------------------- Sub Components -------------------- */

interface SidebarContainerProps extends SidebarProps {
  isAdmin: boolean;
  isAdminPath: boolean;
  adminOpen: boolean;
  setAdminOpen: (v: boolean) => void;
  location: ReturnType<typeof useLocation>;
}

const MobileSidebar: React.FC<SidebarContainerProps> = ({
  setCollapsed,
  mobileOpen,
  isAdmin,
  adminOpen,
  setAdminOpen,
  isAdminPath,
  location,
  adminOnly,
}) => (
  <div className="flex flex-col h-full bg-white dark:bg-[#08070A] overflow-y-auto">
    <SidebarContent
      collapsed={false}
      setCollapsed={setCollapsed}
      mobileOpen={mobileOpen}
      location={location}
      isAdmin={isAdmin}
      adminOpen={adminOpen}
      setAdminOpen={setAdminOpen}
      isAdminPath={isAdminPath}
      adminOnly={adminOnly}
    />
  </div>
);

const DesktopSidebar: React.FC<SidebarContainerProps> = ({
  collapsed,
  setCollapsed,
  mobileOpen,
  isAdmin,
  adminOpen,
  setAdminOpen,
  isAdminPath,
  location,
}) => (
  <aside
    className={cn(
      'fixed left-0 top-0 h-full bg-white dark:bg-[#08070A] border-r border-gray-200 dark:border-gray-800 transition-all duration-300 z-50 overflow-x-hidden',
      collapsed ? 'w-20' : 'w-64',
      'hidden md:block',
    )}
  >
    <SidebarContent
      collapsed={collapsed}
      setCollapsed={setCollapsed}
      mobileOpen={mobileOpen}
      location={location}
      isAdmin={isAdmin}
      adminOpen={adminOpen}
      setAdminOpen={setAdminOpen}
      isAdminPath={isAdminPath}
    />
  </aside>
);

/* -------------------- Main Component -------------------- */

const Sidebar: React.FC<SidebarProps> = ({
  collapsed,
  setCollapsed,
  mobileOpen,
  adminOnly,
}) => {
  const location = useLocation();
  const { user } = useAuth();

  const isAdmin = user?.role === 'admin';
  const isAdminPath = location.pathname.startsWith('/admin');

  const [adminOpen, setAdminOpen] = useState(isAdminPath);

  if (mobileOpen) {
    return (
      <MobileSidebar
        collapsed={collapsed}
        setCollapsed={setCollapsed}
        mobileOpen={mobileOpen}
        isAdmin={isAdmin}
        adminOpen={adminOpen}
        setAdminOpen={setAdminOpen}
        isAdminPath={isAdminPath}
        location={location}
        adminOnly={adminOnly}
      />
    );
  }

  return (
    <DesktopSidebar
      collapsed={collapsed}
      setCollapsed={setCollapsed}
      mobileOpen={mobileOpen}
      isAdmin={isAdmin}
      adminOpen={adminOpen}
      setAdminOpen={setAdminOpen}
      isAdminPath={isAdminPath}
      location={location}
    />
  );
};

export default Sidebar;
