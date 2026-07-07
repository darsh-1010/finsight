import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import Loader from '../common/Loader';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isLoggedIn, isLoading, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <Loader />;
  }

  if (!isLoggedIn) {
    return <Navigate to="/" replace />;
  }

  const exemptFromVerification = ['/payment-success', '/payment-cancel'];
  if (!user?.is_verified && location.pathname !== '/verify-email-pending' && !exemptFromVerification.includes(location.pathname)) {
    return <Navigate to="/verify-email-pending" replace />;
  }

  // Redirect to onboarding if not completed and not already there
  if (!user?.is_onboarded && location.pathname !== '/onboarding' && location.pathname !== '/verify-email-pending' && !exemptFromVerification.includes(location.pathname)) {
    return <Navigate to="/onboarding" replace />;
  }

  // Prevent access to onboarding if already completed
  if (user?.is_onboarded && location.pathname === '/onboarding') {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
