import { Eye, EyeOff } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import React, { useState } from 'react';

import { getStoredVisitingUser } from '../api/auth';
import { useAuth } from '../context/AuthContext';

interface LoginFormProps {
  handleLogin: (e: React.FormEvent) => Promise<void>;
  email: string;
  setEmail: (val: string) => void;
  password: string;
  setPassword: (val: string) => void;
  isSubmitting: boolean;
}

const LoginForm: React.FC<LoginFormProps> = ({
  handleLogin,
  email,
  setEmail,
  password,
  setPassword,
  isSubmitting,
}) => {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <form onSubmit={handleLogin} className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-foreground/80 mb-1.5">Email</label>
        <input
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="w-full px-4 py-3 rounded-xl border border-border/60 bg-background/50 text-foreground placeholder:text-muted-foreground focus:outline-none focus:bg-background focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground/80 mb-1.5">Password</label>
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
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
      </div>
      <div className="flex justify-end -mt-2">
        <Link href="/forgot-password" className="text-sm text-primary hover:underline font-medium">
          Forgot password?
        </Link>
      </div>
      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full py-3.5 bg-primary text-primary-foreground rounded-xl font-bold hover:opacity-95 transition-all active:scale-95 shadow-lg shadow-primary/20 hover:-translate-y-0.5 transform duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isSubmitting ? 'Signing in...' : 'Sign In'}
      </button>
    </form>
  );
};

const useLoginForm = () => {
  const [email, setEmail] = useState(() => getStoredVisitingUser()?.email || '');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  return { email, setEmail, password, setPassword, error, setError, isSubmitting, setIsSubmitting };
};

const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useRouter().push;
  const { email, setEmail, password, setPassword, error, setError, isSubmitting, setIsSubmitting } = useLoginForm();

  const performLogin = async () => {
    try {
      await login({ email, password });
      navigate('/');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string | { msg: string }[] } } };

      let errorMsg = 'Failed to login. Please check your credentials and try again.';

      if (e.response?.data?.detail) {
        if (typeof e.response.data.detail === 'string') {
          errorMsg = e.response.data.detail;
        } else if (Array.isArray(e.response.data.detail) && e.response.data.detail.length > 0) {
          const detailObj = e.response.data.detail[0];

          errorMsg = detailObj?.msg || errorMsg;
        }
      }

      setError(errorMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);
    await performLogin();
  };

  return (
    <div className="relative flex items-center justify-center min-h-[calc(100vh-80px)] overflow-hidden">
      {/* Background blobs */}
      <div className="absolute inset-0 pointer-events-none -z-10">
        <div className="absolute top-[10%] left-[15%] w-[300px] h-[300px] rounded-full bg-primary/5 dark:bg-primary/10 blur-[80px] animate-blob-1" />
        <div className="absolute bottom-[10%] right-[15%] w-[350px] h-[350px] rounded-full bg-accent/5 dark:bg-accent/10 blur-[90px] animate-blob-2" />
      </div>

      <div className="w-full max-w-md px-4 animate-fade-in-up">
        {/* Card */}
        <div className="bg-card/30 backdrop-blur-xl border border-border/50 rounded-3xl p-8 sm:p-10 shadow-2xl shadow-black/10 dark:shadow-black/40">
          {/* Header */}
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-foreground">Welcome back</h2>
            <p className="text-muted-foreground text-sm mt-1.5">Sign in to access your investment intelligence</p>
          </div>

          {error && (
            <div className="mb-6 p-3.5 bg-destructive/10 border border-destructive/20 text-destructive rounded-xl text-sm text-center">
              {error}
            </div>
          )}

          <LoginForm
            handleLogin={handleLogin}
            email={email}
            setEmail={setEmail}
            password={password}
            setPassword={setPassword}
            isSubmitting={isSubmitting}
          />

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{' '}
            <Link href="/signup" className="text-primary font-semibold hover:underline cursor-pointer">
              Sign up free
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
