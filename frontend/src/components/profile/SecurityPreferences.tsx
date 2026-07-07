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
      <div className="flex items-center justify-between py-4 gap-4">
        <div className="flex-1 pr-2">
          <p className="font-semibold">Email Notifications</p>
          <p className="text-xs text-muted-foreground">
            Receive market insights and alert digests.
          </p>
        </div>
        <Button variant="outline" size="sm" disabled className="shrink-0">
          Configure
        </Button>
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
