import React from 'react';

import PasswordChangeDialog from '@/components/profile/PasswordChangeDialog';
import ProfileTabs from '@/components/profile/ProfileTabs';
import { useUserProfile } from '@/hooks/UserProfileHook';

const ProfileHeader: React.FC = () => (
  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
    <div>
      <h1 className="text-2xl font-bold bg-linear-to-r from-primary to-blue-400 bg-clip-text text-transparent">
        User Profile
      </h1>
      <p className="text-muted-foreground mt-1 text-sm">
        Manage your account, tokens, subscription, and security settings.
      </p>
    </div>
  </div>
);

const UserProfile: React.FC = () => {
  const state = useUserProfile();

  return (
    <div className="max-w-5xl mx-auto p-4 md:p-8 space-y-8">
      <ProfileHeader />

      <ProfileTabs
        user={state.user}
        onOpenPasswordModal={() => state.setIsPasswordModalOpen(true)}
      />

      <PasswordChangeDialog
        isOpen={state.isPasswordModalOpen}
        onOpenChange={state.setIsPasswordModalOpen}
        onSubmit={state.handlePasswordChange}
        isSubmitting={state.isSubmitting}
        pwdMsg={state.pwdMsg}
        currentPassword={state.currentPassword}
        setCurrentPassword={state.setCurrentPassword}
        newPassword={state.newPassword}
        setNewPassword={state.setNewPassword}
        confirmPassword={state.confirmPassword}
        setConfirmPassword={state.setConfirmPassword}
      />
    </div>
  );
};

export default UserProfile;
