import React, { useState } from 'react';

import { authApi } from '@/api/auth';
import { useAuth } from '@/context/AuthContext';

/* -------------------- Types -------------------- */

type PasswordMessage =
  | { type: 'success'; text: string }
  | { type: 'error'; text: string }
  | null;

/* -------------------- Utils -------------------- */

const extractErrorMessage = (err: unknown): string => {
  const error = err as { response?: { data?: { detail?: string } } };

  return error.response?.data?.detail || 'Failed to change password';
};

/* -------------------- Small Hooks -------------------- */

const usePasswordForm = () => {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  return {
    currentPassword,
    setCurrentPassword,
    newPassword,
    setNewPassword,
    confirmPassword,
    setConfirmPassword,
  };
};

const usePasswordMeta = () => {
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pwdMsg, setPwdMsg] = useState<PasswordMessage>(null);

  return {
    isPasswordModalOpen,
    setIsPasswordModalOpen,
    isSubmitting,
    setIsSubmitting,
    pwdMsg,
    setPwdMsg,
  };
};

/* -------------------- Logic Helpers -------------------- */

const validatePasswords = (
  newPassword: string,
  confirmPassword: string,
): string | null => {
  if (newPassword !== confirmPassword) {
    return 'New passwords do not match';
  }

  if (newPassword.length < 8) {
    return 'Password must be at least 8 characters';
  }

  return null;
};

const resetPasswordForm = (
  setCurrentPassword: (v: string) => void,
  setNewPassword: (v: string) => void,
  setConfirmPassword: (v: string) => void,
) => {
  setCurrentPassword('');
  setNewPassword('');
  setConfirmPassword('');
};

/* -------------------- Feature Hooks -------------------- */

const usePasswordChange = () => {
  const form = usePasswordForm();
  const meta = usePasswordMeta();

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    meta.setPwdMsg(null);

    const validationError = validatePasswords(
      form.newPassword,
      form.confirmPassword,
    );

    if (validationError) {
      meta.setPwdMsg({ type: 'error', text: validationError });

      return;
    }

    meta.setIsSubmitting(true);

    try {
      await authApi.changePassword({
        current_password: form.currentPassword,
        new_password: form.newPassword,
      });

      meta.setPwdMsg({
        type: 'success',
        text: 'Password changed successfully!',
      });

      resetPasswordForm(
        form.setCurrentPassword,
        form.setNewPassword,
        form.setConfirmPassword,
      );

      setTimeout(() => meta.setIsPasswordModalOpen(false), 2000);
    } catch (err) {
      meta.setPwdMsg({
        type: 'error',
        text: extractErrorMessage(err),
      });
    } finally {
      meta.setIsSubmitting(false);
    }
  };

  return {
    ...form,
    ...meta,
    handlePasswordChange,
  };
};

/* -------------------- Main Hook -------------------- */

export const useUserProfile = () => {
  const { user } = useAuth();
  const password = usePasswordChange();

  return {
    user,
    ...password,
  };
};
