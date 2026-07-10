import { Shield } from 'lucide-react';
import React from 'react';
import { formatDistanceToNow } from 'date-fns';

import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';

interface SecurityPreferencesProps {
  onOpenPasswordModal: () => void;
  embedded?: boolean;
}

const SecurityPreferences: React.FC<SecurityPreferencesProps> = ({
  onOpenPasswordModal,
  embedded = false,
}) => {
  const { user } = useAuth();
  const [optIn, setOptIn] = React.useState(() => {
    if (typeof window === 'undefined') return true;
    return localStorage.getItem("weekly_briefing_opt_in") !== "false";
  });

  const content = (
    <div className="space-y-4">
      <div className="flex items-center justify-between py-4 border-b border-border/50 gap-4">
        <div className="flex-1 pr-2">
          <p className="font-semibold">Password</p>
          <p className="text-xs text-muted-foreground">
            {user?.updated_at &&
              formatDistanceToNow(new Date(user.updated_at), {
                addSuffix: true,
              })}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={onOpenPasswordModal}
        >
          <span className="hidden sm:inline">Change Password</span>
          <span className="sm:hidden">Change</span>
        </Button>
      </div>
      <div className="flex items-center justify-between py-4 gap-4 border-b border-border/50">
        <div className="flex-1 pr-2">
          <p className="font-semibold">Weekly Email Briefings</p>
          <p className="text-xs text-muted-foreground">
            Get a weekly performance digest of trending tickers in your mailbox.
          </p>
        </div>
        {user?.entitlements?.includes("BRIEFINGS_WEEKLY") ? (
          <button
            type="button"
            onClick={() => {
              const nextVal = !optIn;
              localStorage.setItem("weekly_briefing_opt_in", nextVal.toString());
              setOptIn(nextVal);
            }}
            className={`w-11 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-300 ${
              optIn ? "bg-primary" : "bg-gray-300 dark:bg-gray-700"
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform duration-300 ${
                optIn ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-2xs font-extrabold bg-primary/10 text-primary px-2.5 py-1 rounded-full uppercase tracking-wider">
              Institutional Tier
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.location.assign("/pricing")}
              className="shrink-0"
            >
              Upgrade
            </Button>
          </div>
        )}
      </div>
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <section className="bg-card border border-border p-6 rounded-2xl neon-card">
      <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
        <Shield size={20} className="text-primary" />
        Security & Preferences
      </h2>
      {content}
    </section>
  );
};

export default SecurityPreferences;
