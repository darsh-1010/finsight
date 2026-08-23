import Link from 'next/link';
import React, { useState } from 'react';

import { authApi } from '../api/auth';

const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);
    
    try {
      await authApi.forgotPassword({ email });
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send reset email. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative flex items-center justify-center min-h-[calc(100vh-80px)] overflow-hidden">
      {/* Background blobs */}
      <div className="absolute inset-0 pointer-events-none -z-10">
        <div className="absolute top-[10%] left-[15%] w-[300px] h-[300px] rounded-full bg-primary/5 dark:bg-primary/10 blur-[80px] animate-blob-1" />
        <div className="absolute bottom-[10%] right-[15%] w-[350px] h-[350px] rounded-full bg-accent/5 dark:bg-accent/10 blur-[90px] animate-blob-2" />
      </div>

      <div className="w-full max-w-md px-4 animate-fade-in-up">
        <div className="bg-card border border-border/60 rounded-3xl p-8 sm:p-10 shadow-xl shadow-black/5 dark:shadow-black/30">
          {/* Header */}
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-foreground">Forgot Password</h2>
            <p className="text-muted-foreground text-sm mt-1.5">We'll send a reset link to your email</p>
          </div>
          
          {success ? (
            <div className="text-center">
              <div className="p-4 bg-primary/10 border border-primary/20 rounded-2xl mb-6">
                <p className="text-foreground text-sm leading-relaxed">
                  If an account exists with this email, a reset link has been sent. Please check your inbox.
                </p>
              </div>
              <Link
                href="/login"
                className="w-full inline-block py-3.5 bg-primary text-primary-foreground rounded-xl font-bold hover:opacity-95 transition-all shadow-lg shadow-primary/20 text-center"
              >
                Return to Login
              </Link>
            </div>
          ) : (
            <>
              {error && (
                <div className="mb-6 p-3.5 bg-destructive/10 border border-destructive/20 text-destructive rounded-xl text-sm text-center">
                  {error}
                </div>
              )}
              
              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-foreground/80 mb-1.5">Email address</label>
                  <input
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full px-4 py-3 rounded-xl border border-border bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-3.5 bg-primary text-primary-foreground rounded-xl font-bold hover:opacity-95 transition-all active:scale-95 shadow-lg shadow-primary/20 hover:-translate-y-0.5 transform duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? 'Sending...' : 'Send Reset Link'}
                </button>
              </form>
              
              <p className="mt-6 text-center text-sm text-muted-foreground">
                Remember your password?{' '}
                <Link href="/login" className="text-primary font-semibold hover:underline cursor-pointer">
                  Sign In
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
