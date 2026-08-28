import { Loader2, Mail, CheckCircle2, ExternalLink } from 'lucide-react';
import { useRouter } from 'next/navigation';
import React, { useState, useEffect } from 'react';

import { authApi } from '../api/auth';
import { Button } from '../components/ui/button';
import { useAuth } from '../context/AuthContext';
import { useAppSelector } from '../store/hooks';
import { selectTiers } from '../store/slices/tierSlice';


const EmailVerificationNotice: React.FC = () => {
  const { user, updateUser, logout } = useAuth();
  const tiers = useAppSelector(selectTiers);
  const navigate = useRouter().push;
  
  const [resending, setResending] = useState(false);
  const [resendStatus, setResendStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (user?.is_verified) {
      navigate('/dashboard');
    }
  }, [user, navigate]);

  const handleResend = async () => {
    setResending(true);
    setResendStatus('idle');
    try {
      await authApi.resendVerification();
      setResendStatus('success');
    } catch (err) {
      setResendStatus('error');
    } finally {
      setResending(false);
    }
  };

  const handleCheckVerified = async () => {
    setChecking(true);
    await updateUser();
    setChecking(false);
  };

  const selectedTier = tiers.find(t => t.level === user?.tier_level);

  const getEmailProviderLink = (email: string) => {
    if (!email) return null;
    const domain = email.split('@')[1]?.toLowerCase();

    if (domain === 'gmail.com') return { name: 'Gmail', url: 'https://mail.google.com/' };
    if (domain === 'yahoo.com' || domain === 'ymail.com') return { name: 'Yahoo Mail', url: 'https://mail.yahoo.com/' };
    if (domain === 'outlook.com' || domain === 'hotmail.com') return { name: 'Outlook', url: 'https://outlook.live.com/' };

    return { name: 'Gmail', url: 'https://mail.google.com/' };
  };

  const emailProvider = getEmailProviderLink(user?.email || '');

  return (
    <div className="w-full max-w-lg z-10 relative flex flex-col items-center text-center px-6">
      <div className="flex justify-center mb-8">
        <div className="w-24 h-24 rounded-full bg-primary/10 flex items-center justify-center">
          <Mail size={56} className="text-primary" />
        </div>
      </div>
      
      <h2 className="text-4xl md:text-5xl font-bold mb-6 text-gray-900 dark:text-white tracking-tight">Welcome to FinSight!</h2>
      <p className="text-lg text-gray-600 dark:text-gray-300 mb-10 max-w-md">
        We've sent a verification link to <strong className="text-foreground">{user?.email}</strong>. 
        Please check your email and click the link to verify your account and get started.
      </p>

      {selectedTier && selectedTier.level > 1 && (
        <div className="mb-10 p-5 bg-background/50 backdrop-blur-sm rounded-2xl text-left border border-white/10 w-full shadow-xl">
          <h3 className="font-semibold text-lg mb-3">Your Selected Plan: {selectedTier.name}</h3>
          <ul className="space-y-3 text-sm text-muted-foreground">
            <li className="flex items-start"><CheckCircle2 className="w-5 h-5 mr-3 text-primary shrink-0" /> <span className="mt-0.5">Full access to premium features</span></li>
            <li className="flex items-start"><CheckCircle2 className="w-5 h-5 mr-3 text-primary shrink-0" /> <span className="mt-0.5">Unlocked insights and tools</span></li>
          </ul>
        </div>
      )}

      <div className="space-y-4 w-full max-w-sm">
        {emailProvider && (
          <Button 
            onClick={() => window.open(emailProvider.url, '_blank')}
            className="w-full py-6 text-lg font-semibold rounded-xl shadow-lg shadow-primary/20 hover:scale-105 transition-transform"
          >
            Open {emailProvider.name} <ExternalLink className="w-5 h-5 ml-2" />
          </Button>
        )}

        <Button 
          variant={emailProvider ? 'outline' : 'default'}
          onClick={handleCheckVerified} 
          disabled={checking}
          className={`w-full py-6 text-lg font-semibold rounded-xl transition-transform ${emailProvider ? 'border-white/10 bg-background/50 backdrop-blur-md hover:bg-background/80' : 'shadow-lg shadow-primary/20 hover:scale-105'}`}
        >
          {checking ? <Loader2 className="w-5 h-5 animate-spin" /> : 'I have verified my email'}
        </Button>

        <div className="pt-4">
          <Button 
            variant="ghost" 
            onClick={handleResend}
            disabled={resending || resendStatus === 'success'}
            className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors hover:bg-transparent"
          >
            {resending ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
            {resendStatus === 'success' ? 'Verification Email Sent!' : "Didn't receive the email? Resend"}
          </Button>
          {resendStatus === 'error' && (
            <p className="text-sm text-red-500 mt-2">Failed to resend email. Please try again later.</p>
          )}
        </div>

        <div className="pt-4">
          <Button 
            variant="link" 
            onClick={logout}
            className="text-sx text-muted-foreground hover:text-red-500 transition-colors"
          >
            Wrong account? Log out
          </Button>
        </div>
      </div>
    </div>
  );
};

export default EmailVerificationNotice;
