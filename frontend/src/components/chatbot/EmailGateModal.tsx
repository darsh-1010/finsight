import { useRouter } from 'next/navigation';
import React, { useState } from 'react';
import { PiEnvelopeSimpleFill, PiWarningCircleFill, PiArrowRightBold } from 'react-icons/pi';

import {
  visitingUsersApi,
  storeVisitingUser,
  isRegisteredUserError,
  type VisitingUser,
} from '@/api/auth';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface EmailGateModalProps {
  isOpen: boolean;
  onSuccess: (visitingUser: VisitingUser) => void;
}

type ModalView = 'email-form' | 'already-registered';

const EmailGateModal: React.FC<EmailGateModalProps> = ({ isOpen, onSuccess }) => {
  const navigate = useRouter().push;
  const [view, setView] = useState<ModalView>('email-form');
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const validateEmail = (value: string) => {
    if (!value.trim()) return 'Email is required';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'Please enter a valid email';

    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);

    const validationError = validateEmail(email);

    if (validationError) {
      setEmailError(validationError);

      return;
    }
    setEmailError(null);
    setIsLoading(true);

    try {
      const visitingUser = await visitingUsersApi.register(email.trim().toLowerCase());

      storeVisitingUser(visitingUser);
      onSuccess(visitingUser);
    } catch (err: unknown) {
      if (isRegisteredUserError(err)) {
        setView('already-registered');
      } else {
        setApiError('Something went wrong. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog
      open={isOpen}
      
      // Non-dismissible — user must complete the gate
      // onOpenChange={() => undefined}
    >
      <DialogContent
        className="sm:max-w-md bg-white dark:bg-[#08070A] border-gray-100 dark:border-gray-800 shadow-2xl rounded-3xl"
        hideCloseButton
        onInteractOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        {view === 'email-form' ? (
          <>
            <DialogHeader className="flex flex-col items-center pt-6">
              <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-6">
                <PiEnvelopeSimpleFill className="text-primary text-3xl" />
              </div>
              <DialogTitle className="text-2xl font-bold text-center">
                Try FinSight for Free
              </DialogTitle>
              <DialogDescription className="text-center text-muted-foreground mt-3 text-base leading-relaxed">
                Enter your email to get&nbsp;
                <span className="font-semibold text-foreground">5 free messages</span>
                &nbsp;with FinSight's AI-powered investment intelligence.
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleSubmit} className="mt-6 space-y-4 pb-4">
              <div className="space-y-1">
                <input
                  id="visiting-user-email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (emailError) setEmailError(null);
                    if (apiError) setApiError(null);
                  }}
                  placeholder="you@example.com"
                  autoFocus
                  autoComplete="email"
                  className={[
                    'w-full px-4 py-3 rounded-xl border text-sm bg-background',
                    'focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all',
                    emailError
                      ? 'border-destructive focus:ring-destructive/30'
                      : 'border-gray-200 dark:border-gray-700',
                  ].join(' ')}
                />
                {emailError && (
                  <p className="text-xs text-destructive flex items-center gap-1 pl-1">
                    <PiWarningCircleFill size={14} />
                    {emailError}
                  </p>
                )}
                {apiError && (
                  <p className="text-xs text-destructive flex items-center gap-1 pl-1">
                    <PiWarningCircleFill size={14} />
                    {apiError}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                disabled={isLoading}
                className="w-full py-6 text-base rounded-xl shadow-lg shadow-primary/20 flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <span className="animate-pulse">Checking…</span>
                ) : (
                  <>
                    Start Chatting <PiArrowRightBold />
                  </>
                )}
              </Button>

              <div className="flex flex-col gap-4 pt-2">
                <p className="text-center text-sm text-muted-foreground">
                  Already have an account?{' '}
                  <button
                    type="button"
                    onClick={() => navigate('/login')}
                    className="text-primary font-medium underline underline-offset-4 hover:opacity-80 transition-opacity cursor-pointer"
                  >
                    Log in
                  </button>
                </p>

                <div className="flex items-center justify-center">
                  <div className="h-[1px] w-12 bg-gray-200 dark:bg-gray-800 rounded"></div>
                  <span className="px-3 text-xs text-muted-foreground uppercase tracking-wider">or</span>
                  <div className="h-[1px] w-12 bg-gray-200 dark:bg-gray-800 rounded"></div>
                </div>

                <button
                  type="button"
                  onClick={() => navigate('/')}
                  className="text-center text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                >
                  Return to Home Page
                </button>
              </div>
            </form>
          </>
        ) : (
          /* ─── Already-registered view ─── */
          <>
            <DialogHeader className="flex flex-col items-center pt-6">
              <div className="w-16 h-16 bg-indigo-500/10 rounded-full flex items-center justify-center mb-6">
                <PiWarningCircleFill className="text-indigo-500 text-3xl" />
              </div>
              <DialogTitle className="text-2xl font-bold text-center">
                You Already Have an Account
              </DialogTitle>
              <DialogDescription className="text-center text-muted-foreground mt-3 text-base leading-relaxed">
                <span className="font-medium text-foreground break-all">{email}</span>
                &nbsp;is registered with FinSight. Please log in to continue with your
                full account.
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col gap-3 mt-8 pb-4">
              <Button
                className="w-full py-6 text-base rounded-xl shadow-lg shadow-primary/20"
                onClick={() => navigate('/login')}
              >
                Log In to FinSight
              </Button>
              <Button
                variant="outline"
                className="w-full py-6 text-base rounded-xl border-gray-200 dark:border-gray-800"
                onClick={() => {
                  setView('email-form');
                  setEmail('');
                  setApiError(null);
                }}
              >
                Use a Different Email
              </Button>
              
              <div className="flex items-center justify-center mt-3">
                <div className="h-[1px] w-12 bg-gray-200 dark:bg-gray-800 rounded"></div>
                <span className="px-3 text-xs text-muted-foreground uppercase tracking-wider">or</span>
                <div className="h-[1px] w-12 bg-gray-200 dark:bg-gray-800 rounded"></div>
              </div>

              <button
                type="button"
                onClick={() => navigate('/')}
                className="text-center text-sm text-muted-foreground hover:text-foreground transition-colors mt-1"
              >
                Return to Home Page
              </button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default EmailGateModal;
