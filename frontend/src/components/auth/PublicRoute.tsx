import React from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';


interface PublicRouteProps {
  children: React.ReactNode;
}

const PublicRoute: React.FC<PublicRouteProps> = ({ children }) => {
  const { isLoggedIn, isLoading, user } = useAuth();
  
  if (isLoading) {
    // Or return null, or a spinner
    return <div className="flex justify-center items-center h-screen">Loading...</div>;
  }

  if (isLoggedIn) {
    if (user?.role === 'admin') {
      return <Navigate to="/admin" replace />;
    }
    
    if (!user?.is_verified) {
      return <Navigate to="/verify-email-pending" replace />;
    }
    
    return <Navigate to={user?.is_onboarded ? '/dashboard' : '/onboarding'} replace />;
  }

  return <>{children}</>;
};

export default PublicRoute;
