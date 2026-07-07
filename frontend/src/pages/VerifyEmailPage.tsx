import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/auth';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';

const VerifyEmailPage: React.FC = () => {
  const { updateUser } = useAuth();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const hasAttempted = useRef(false);

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Invalid or missing verification token.');
      return;
    }

    if (hasAttempted.current) return;
    hasAttempted.current = true;

    const verify = async () => {
      try {
        await authApi.verifyEmail(token);
        await updateUser();
        setStatus('success');
        setMessage('Your email has been successfully verified! You can now access all features.');
      } catch (err: any) {
        setStatus('error');
        setMessage(err.response?.data?.detail || 'Verification failed. The link may have expired or is invalid.');
      }
    };

    verify();
  }, [token]);

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-80px)] p-4">
      <div className="bg-white dark:bg-[#08070A] p-10 rounded-2xl shadow-2xl w-full max-w-md border border-gray-200 dark:border-gray-800 text-center">
        {status === 'loading' && (
          <div className="flex flex-col items-center">
            <Loader2 size={48} className="animate-spin text-primary mb-6" />
            <h2 className="text-2xl font-bold mb-2 text-gray-800 dark:text-white">Verifying Email...</h2>
            <p className="text-gray-500 dark:text-gray-400">Please wait while we confirm your email address.</p>
          </div>
        )}
        
        {status === 'success' && (
          <div className="flex flex-col items-center">
            <CheckCircle size={56} className="text-green-500 mb-6" />
            <h2 className="text-2xl font-bold mb-4 text-gray-800 dark:text-white">Email Verified!</h2>
            <p className="text-gray-600 dark:text-gray-300 mb-8">{message}</p>
            <Link 
              to="/dashboard" 
              className="w-full py-3 bg-primary text-primary-foreground rounded-lg font-bold hover:bg-primary/90 transition-all active:scale-95 shadow-md inline-block"
            >
              Go to Dashboard
            </Link>
          </div>
        )}

        {status === 'error' && (
          <div className="flex flex-col items-center">
            <XCircle size={56} className="text-red-500 mb-6" />
            <h2 className="text-2xl font-bold mb-4 text-gray-800 dark:text-white">Verification Failed</h2>
            <p className="text-gray-600 dark:text-gray-300 mb-8">{message}</p>
            <Link 
              to="/user_profile" 
              className="w-full py-3 border border-border text-foreground rounded-lg font-bold hover:bg-secondary/80 transition-all inline-block"
            >
              Back to Profile
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};

export default VerifyEmailPage;
