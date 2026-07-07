import { Loader2, Shield, Eye, EyeOff } from 'lucide-react';
import React, { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';

/* -------------------- Types -------------------- */

interface PasswordChangeDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (e: React.FormEvent) => Promise<void>;
  isSubmitting: boolean;
  pwdMsg: { type: 'success' | 'error'; text: string } | null;
  currentPassword: string;
  setCurrentPassword: (v: string) => void;
  newPassword: string;
  setNewPassword: (v: string) => void;
  confirmPassword: string;
  setConfirmPassword: (v: string) => void;
}

/* -------------------- Small Components -------------------- */

const PasswordInput = ({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) => {
  const [showPassword, setShowPassword] = useState(false);
  
  return (
    <div className="space-y-2">
      <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
        {label}
      </label>
      <div className="relative">
        <input
          type={showPassword ? "text" : "password"}
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-secondary/50 border border-border rounded-xl px-4 py-2.5 pr-10 outline-hidden focus:ring-2 focus:ring-primary/50 transition-all font-mono"
          placeholder="••••••••"
        />
        <button
          type="button"
          onClick={() => setShowPassword(!showPassword)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-200 transition-colors"
        >
          {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
    </div>
  );
};

const MessageBanner = ({
  msg,
}: {
  msg: { type: 'success' | 'error'; text: string };
}) => (
  <div
    className={`text-xs p-3 rounded-lg border animate-in fade-in slide-in-from-top-1 ${
      msg.type === 'success'
        ? 'bg-green-500/10 border-green-500/20 text-green-500'
        : 'bg-red-500/10 border-red-500/20 text-red-500'
    }`}
  >
    {msg.text}
  </div>
);

const SubmitButton = ({
  isSubmitting,
}: {
  isSubmitting: boolean;
}) => (
  <Button
    type="submit"
    disabled={isSubmitting}
    className="w-full bg-primary hover:bg-blue-600 text-white font-bold rounded-xl"
  >
    {isSubmitting ? (
      <Loader2 className="animate-spin" size={18} />
    ) : (
      'Update Password'
    )}
  </Button>
);

/* -------------------- Form -------------------- */

const PasswordForm = ({
  onSubmit,
  currentPassword,
  setCurrentPassword,
  newPassword,
  setNewPassword,
  confirmPassword,
  setConfirmPassword,
  pwdMsg,
  isSubmitting,
}: Omit<PasswordChangeDialogProps, 'isOpen' | 'onOpenChange'>) => (
  <form onSubmit={onSubmit} className="space-y-4 py-4">
    <PasswordInput
      label="Current Password"
      value={currentPassword}
      onChange={setCurrentPassword}
    />

    <PasswordInput
      label="New Password"
      value={newPassword}
      onChange={setNewPassword}
    />

    <PasswordInput
      label="Confirm New Password"
      value={confirmPassword}
      onChange={setConfirmPassword}
    />

    {pwdMsg && <MessageBanner msg={pwdMsg} />}

    <DialogFooter className="pt-4">
      <SubmitButton isSubmitting={isSubmitting} />
    </DialogFooter>
  </form>
);

/* -------------------- Main Component -------------------- */

const PasswordChangeDialog: React.FC<PasswordChangeDialogProps> = ({
  isOpen,
  onOpenChange,
  ...formProps
}) => (
  <Dialog open={isOpen} onOpenChange={onOpenChange}>
    <DialogContent className="sm:max-w-md bg-card border-border neon-card">
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <Shield className="text-primary" size={20} />
          Change Password
        </DialogTitle>
      </DialogHeader>

      <PasswordForm {...formProps} />
    </DialogContent>
  </Dialog>
);

export default PasswordChangeDialog;