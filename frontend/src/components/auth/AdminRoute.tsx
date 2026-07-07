import React from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import Loader from '../common/Loader';

interface AdminRouteProps {
  children: React.ReactNode;
}

const AdminRoute: React.FC<AdminRouteProps> = ({ children }) => {
  const { isLoggedIn, isLoading, user } = useAuth();

  if (isLoading) {
    return <Loader />;
  }

  if (!isLoggedIn || user?.role !== 'admin') {
    return <Navigate to={!isLoggedIn ? '/' : '/dashboard'} replace />;
  }

  return <>{children}</>;
};

export default AdminRoute;
