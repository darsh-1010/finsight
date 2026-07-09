import React, { useEffect, useState } from 'react';
import { useNavigate, Link, useSearchParams } from 'react-router-dom';
import { Eye, EyeOff } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { getStoredVisitingUser } from '../api/auth';


import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { fetchTiers, selectTiers, selectTiersLoading, selectTiersError } from '@/store/slices/tierSlice';

interface TierInfoProps {
  isLoading: boolean;
  tierError: string | null;
  tierLevel: number;
  tierName: string;
}

const TierInfo: React.FC<TierInfoProps> = ({ isLoading, tierError, tierLevel, tierName }) => {
  if (tierLevel <= 1) return null;

  return (
    <div className="mb-4 p-3.5 bg-primary/10 border border-primary/20 text-primary rounded-xl text-sm text-center">
      {isLoading ? (
        'Loading tier information...'
      ) : tierError ? (
        <span className="text-destructive">{tierError}</span>
      ) : (
        <>Selected Tier: <strong>{tierName}</strong></>
      )}
    </div>
  );
};

interface SignupFormProps {
  formData: {
    email: string;
    password: string;
    confirmPassword: string;
    role_id: number;
    tier_level: number;
    billing_period: 'monthly' | 'yearly';
  };
  handleChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleSignup: (e: React.FormEvent) => Promise<void>;
  isSubmitting: boolean;
}

const SignupForm: React.FC<SignupFormProps> = ({ formData, handleChange, handleSignup, isSubmitting }) => {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  return (
    <form onSubmit={handleSignup} className="space-y-4">
      <input
        type="email"
        name="email"
        placeholder="Email"
        value={formData.email}
        onChange={handleChange}
        required
        className="w-full px-4 py-3 rounded-xl border border-border/60 bg-background/50 text-foreground placeholder:text-muted-foreground focus:outline-none focus:bg-background focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
      />
      <div className="relative">
        <input
          type={showPassword ? "text" : "password"}
          name="password"
          placeholder="Password"
          value={formData.password}
          onChange={handleChange}
          required
          className="w-full px-4 py-3 pr-11 rounded-xl border border-border/60 bg-background/50 text-foreground placeholder:text-muted-foreground focus:outline-none focus:bg-background focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
        />
        <button
          type="button"
          onClick={() => setShowPassword(!showPassword)}
          className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
        >
          {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
      <div className="relative">
        <input
          type={showConfirmPassword ? "text" : "password"}
          name="confirmPassword"
          placeholder="Confirm Password"
          value={formData.confirmPassword}
          onChange={handleChange}
          required
          className="w-full px-4 py-3 pr-11 rounded-xl border border-border/60 bg-background/50 text-foreground placeholder:text-muted-foreground focus:outline-none focus:bg-background focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
        />
        <button
          type="button"
          onClick={() => setShowConfirmPassword(!showConfirmPassword)}
          className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
        >
          {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full py-3.5 bg-primary text-primary-foreground rounded-xl font-bold hover:opacity-95 transition-all active:scale-95 shadow-lg shadow-primary/20 hover:-translate-y-0.5 transform duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isSubmitting ? 'Creating Account...' : 'Create Account'}
      </button>
    </form>
  );
};

const useTierSelection = (searchParams: URLSearchParams) => {
  const tierParam = searchParams.get('tier');
  const planParam = searchParams.get('plan');

  const tier = tierParam ? parseInt(tierParam) : 1;
  const period = planParam === 'yearly' ? 'yearly' as const : 'monthly' as const;

  return { tier: tier >= 1 && tier <= 5 ? tier : 1, period };
};

interface Tier {
  level: number;
  name: string;
  price_amount: string | number;
  price_amount_yearly?: string | number | null;
}

const performSignup = (
  formData: { email: string; password: string; role_id: number; tier_level: number; billing_period: string },
  signup: (data: { email: string; password: string; role_id: number; tier_level: number }) => Promise<void>,
  navigate: (path: string) => void,
  setError: (msg: string) => void,
  setIsSubmitting: (loading: boolean) => void
) => {
  setError('');
  setIsSubmitting(true);

  signup({
    email: formData.email,
    password: formData.password,
    role_id: Number(formData.role_id),
    tier_level: Number(formData.tier_level),
  }).then(() => {
    localStorage.setItem('has_shown_welcome_modal', 'true');
    navigate('/onboarding');
  }).catch((err: unknown) => {
    const e = err as { response?: { data?: { detail?: string | { msg: string }[] } } };

    let errorMsg = 'Failed to sign up. Please verify your details and try again.';
    if (e.response?.data?.detail) {
      if (typeof e.response.data.detail === 'string') {
        errorMsg = e.response.data.detail;
      } else if (Array.isArray(e.response.data.detail) && e.response.data.detail.length > 0) {
        const detailObj = e.response.data.detail[0];
        errorMsg = detailObj?.msg || errorMsg;
      }
    }

    setError(errorMsg);
  }).finally(() => {
    setIsSubmitting(false);
  });
};

const useSignupForm = (initialSelection: { tier: number; period: 'monthly' | 'yearly' }) => {
  const [formData, setFormData] = useState({
    email: getStoredVisitingUser()?.email || '',
    password: '',
    confirmPassword: '',
    role_id: 2,
    ...initialSelection,
    tier_level: initialSelection.tier,
    billing_period: initialSelection.period,
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  return { formData, handleChange };
};

const useSignupActions = () => {
  const { signup } = useAuth();
  const navigate = useNavigate();

  return { signup, navigate };
};

const useSignupStatus = () => {
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  return { error, setError, isSubmitting, setIsSubmitting };
};

const useSignupLogic = () => {
  const [searchParams] = useSearchParams();
  const { signup, navigate } = useSignupActions();
  const initialSelection = useTierSelection(searchParams);
  const { formData, handleChange } = useSignupForm(initialSelection);
  const { error, setError, isSubmitting, setIsSubmitting } = useSignupStatus();

  const handleSignupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');

      return;
    }

    if (formData.tier_level !== 1) {
      sessionStorage.setItem('payment_redirect_pending', 'true');
    }

    performSignup(formData, signup, navigate, setError, setIsSubmitting);
  };

  return { formData, error, isSubmitting, handleChange, handleSignupSubmit };
};

const getSelectedTierDetails = (tiers: Tier[], tierLevel: number, period: string) => {
  const selectedTier = tiers.find((t) => t.level === tierLevel);

  if (!selectedTier) return 'Foundation (Free)';

  const price = period === 'yearly'
    ? (Number(selectedTier.price_amount_yearly) || (Number(selectedTier.price_amount) * 12 * 0.9)) / 100
    : Number(selectedTier.price_amount) / 100;

  return `${selectedTier.name} ($${Math.round(price)}/${period === 'yearly' ? 'yr' : 'mo'})`;
};

const useTiers = () => {
  const dispatch = useAppDispatch();
  const tiers = useAppSelector(selectTiers);
  const isLoading = useAppSelector(selectTiersLoading);
  const tierError = useAppSelector(selectTiersError);

  useEffect(() => {
    dispatch(fetchTiers());
  }, [dispatch]);

  return { tiers, isLoading, tierError };
};

const SignupPage: React.FC = () => {
  const { tiers, isLoading, tierError } = useTiers();
  const { formData, error, isSubmitting, handleChange, handleSignupSubmit } = useSignupLogic();
  const tierName = getSelectedTierDetails(tiers, formData.tier_level, formData.billing_period);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="relative flex items-center justify-center min-h-[calc(100vh-80px)] overflow-hidden">
      {/* Background blobs */}
      <div className="absolute inset-0 pointer-events-none -z-10">
        <div className="absolute top-[10%] left-[15%] w-[300px] h-[300px] rounded-full bg-primary/5 dark:bg-primary/10 blur-[80px] animate-blob-1" />
        <div className="absolute bottom-[10%] right-[15%] w-[350px] h-[350px] rounded-full bg-accent/5 dark:bg-accent/10 blur-[90px] animate-blob-2" />
      </div>

      <div className="w-full max-w-md px-4 py-12 animate-fade-in-up">
        <div className="bg-card/30 backdrop-blur-xl border border-border/50 rounded-3xl p-8 sm:p-10 shadow-2xl shadow-black/10 dark:shadow-black/40">
          {/* Header */}
          <div className="text-center mb-8">
            <Link to="/" className="inline-flex items-center gap-2 mb-6 hover:opacity-80 transition-opacity">
              <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center text-white font-bold text-lg">F</span>
              <span className="text-xl font-bold tracking-wide bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">FinSight</span>
            </Link>
            <h2 className="text-2xl font-bold text-foreground">Create your account</h2>
            <p className="text-muted-foreground text-sm mt-1.5">Join 200+ investors making smarter decisions</p>
          </div>

          <TierInfo
            isLoading={isLoading}
            tierError={tierError}
            tierLevel={formData.tier_level}
            tierName={tierName}
          />

          {error && (
            <div className="mb-6 p-3.5 bg-destructive/10 border border-destructive/20 text-destructive rounded-xl text-sm text-center">
              {error}
            </div>
          )}

          <SignupForm
            formData={formData}
            handleChange={handleChange}
            handleSignup={handleSignupSubmit}
            isSubmitting={isSubmitting}
          />

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link to="/login" className="text-primary font-semibold hover:underline cursor-pointer">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default SignupPage;
