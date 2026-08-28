import { CreditCard, Shield, User } from 'lucide-react';
import React, { useEffect, useMemo } from 'react';
import { PiCoinsDuotone } from 'react-icons/pi';


import type { User as UserInterface } from '@/api/auth';
import BillingSubscription from '@/components/profile/BillingSubscription';
import PersonalInfo from '@/components/profile/PersonalInfo';
import SecurityPreferences from '@/components/profile/SecurityPreferences';
import TokenUsage from '@/components/profile/TokenUsage';
import { useSearchParams, useUpdateSearchParams } from '@/hooks/useSearchParamsUpdater';
import { isProfileTab, type ProfileTabId } from '@/lib/profileRoutes';
import { cn } from '@/lib/utils';

export { type ProfileTabId } from '@/lib/profileRoutes';

interface ProfileTabsProps {
  user: UserInterface | null;
  onOpenPasswordModal: () => void;
}

interface TabConfig {
  id: ProfileTabId;
  label: string;
  shortLabel: string;
  description: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

const TABS: TabConfig[] = [
  {
    id: 'personal',
    label: 'Personal Information',
    shortLabel: 'Personal',
    description: 'Your account details and trading preferences.',
    icon: User,
  },
  {
    id: 'tokens',
    label: 'Token Information',
    shortLabel: 'Tokens',
    description: 'View your token usage and refill details.',
    icon: PiCoinsDuotone,
  },
  {
    id: 'subscription',
    label: 'Subscription',
    shortLabel: 'Plan',
    description: 'Your active plan and subscription management.',
    icon: CreditCard,
  },
  {
    id: 'security',
    label: 'Security',
    shortLabel: 'Security',
    description: 'Password and notification preferences.',
    icon: Shield,
  },
];

const TabButton: React.FC<{
  tab: TabConfig;
  active: boolean;
  onClick: () => void;
}> = ({ tab, active, onClick }) => {
  const Icon = tab.icon;

  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-3 sm:px-4 py-2.5 rounded-xl text-sm font-medium transition-all whitespace-nowrap shrink-0 cursor-pointer',
        active
          ? 'bg-background text-primary shadow-sm ring-1 ring-border'
          : 'text-muted-foreground hover:text-foreground hover:bg-background/50',
      )}
    >
      <Icon size={18} className={active ? 'text-primary' : undefined} />
      <span className="hidden sm:inline">{tab.label}</span>
      <span className="sm:hidden">{tab.shortLabel}</span>
    </button>
  );
};

const TabPanel: React.FC<{
  tab: TabConfig;
  children: React.ReactNode;
}> = ({ tab, children }) => (
  <div
    role="tabpanel"
    className="bg-card border border-border rounded-2xl neon-card p-6 md:p-8 min-h-80"
  >
    <div className="mb-6 pb-4 border-b border-border/50 flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-4">
      <h2 className="text-xl font-semibold flex items-center gap-2">
        <tab.icon size={22} className="text-primary shrink-0" />
        {tab.label}
      </h2>
      <p className="text-sm text-muted-foreground sm:mt-1 sm:text-right">{tab.description}</p>
    </div>
    {children}
  </div>
);

const ProfileTabs: React.FC<ProfileTabsProps> = ({
  user,
  onOpenPasswordModal,
}) => {
  const searchParams = useSearchParams();
  const setSearchParams = useUpdateSearchParams();

  const tabParam = searchParams.get('tab');
  const activeTab = useMemo(
    () => (isProfileTab(tabParam) ? tabParam : 'personal'),
    [tabParam],
  );

  useEffect(() => {
    if (tabParam && !isProfileTab(tabParam)) {
      setSearchParams({ tab: 'personal' }, { replace: true });
    }
  }, [tabParam, setSearchParams]);

  const setActiveTab = (id: ProfileTabId) => {
    setSearchParams({ tab: id }, { replace: true });
  };

  const activeTabConfig = TABS.find((t) => t.id === activeTab) ?? TABS[0];

  const renderPanel = () => {
    switch (activeTab) {
    case 'personal':
      return <PersonalInfo user={user} embedded />;
    case 'tokens':
      return <TokenUsage embedded />;
    case 'subscription':
      return <BillingSubscription user={user} embedded />;
    case 'security':
      return (
        <SecurityPreferences
          onOpenPasswordModal={onOpenPasswordModal}
          embedded
        />
      );
    default:
      return null;
    }
  };

  return (
    <div className="space-y-6">
      <div
        role="tablist"
        aria-label="Profile sections"
        className="flex justify-between gap-1.5 overflow-x-auto pb-1 scrollbar-thin bg-secondary/30 dark:bg-secondary/10 p-1.5 rounded-2xl border border-border/50"
      >
        {TABS.map((tab) => (
          <TabButton
            key={tab.id}
            tab={tab}
            active={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
          />
        ))}
      </div>

      <TabPanel tab={activeTabConfig}>{renderPanel()}</TabPanel>
    </div>
  );
};

export default ProfileTabs;
