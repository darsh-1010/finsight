import { type FC, lazy, Suspense } from 'react';
import { useRoutes, Navigate } from 'react-router-dom';


import AdminRoute from '../components/auth/AdminRoute';
import ProtectedRoute from '../components/auth/ProtectedRoute';
import PublicRoute from '../components/auth/PublicRoute';
import Loader from '../components/common/Loader';
import { useAuth } from '../context/AuthContext';
import MinimalLayout from '../layouts/MinimalLayout';
import ProtectedRouteLayout from '../layouts/ProtectedRouteLayout';
import PublicLayout from '../layouts/PublicLayout';

// Lazy load page components
const AboutUs = lazy(() => import('../pages/AboutUs'));
const Dashboard = lazy(() => import('../pages/Dashboard'));
const LandingPage = lazy(() => import('../pages/LandingPage'));
const LoginPage = lazy(() => import('../pages/LoginPage'));
const ForgotPasswordPage = lazy(() => import('../pages/ForgotPasswordPage'));
const ResetPasswordPage = lazy(() => import('../pages/ResetPasswordPage'));
const VerifyEmailPage = lazy(() => import('../pages/VerifyEmailPage'));
const EmailVerificationNotice = lazy(() => import('../pages/EmailVerificationNotice'));
const PaymentCancel = lazy(() => import('../pages/PaymentCancel'));
const PaymentSuccess = lazy(() => import('../pages/PaymentSuccess'));
const Pricing = lazy(() => import('../pages/Pricing'));
const Product = lazy(() => import('../pages/Product'));
const SignupPage = lazy(() => import('../pages/SignupPage'));
const TryAskFinSight = lazy(() => import('../pages/TryAskFinSight'));

// Admin and Protected pages
const AdminBrokersPage = lazy(() => import('@/pages/admin/AdminBrokersPage'));
const AdminDashboard = lazy(() => import('@/pages/admin/AdminDashboard'));
const AdminInsightsPage = lazy(() => import('@/pages/admin/AdminInsightsPage'));
const AdminScrapingPage = lazy(() => import('@/pages/admin/AdminScrapingPage'));
const AskFinSight = lazy(() => import('@/pages/AskFinSight'));
const MarketInsigts = lazy(() => import('@/pages/MarketInsigts'));
const UserOnboarding = lazy(() => import('@/pages/UserOnboarding'));
const UserProfile = lazy(() => import('@/pages/UserProfile'));


const HomeRoute = () => {
  const { isLoggedIn, isLoading, user } = useAuth();

  if (isLoading) {
    return <Loader />;
  }

  return isLoggedIn ? (
    <Navigate to={user?.is_onboarded ? '/dashboard' : '/onboarding'} replace />
  ) : (
    <LandingPage />
  );
};

const routesConfig = [
  {
    element: (
      <PublicRoute>
        <PublicLayout />
      </PublicRoute>
    ),
    children: [
      { path: '/', element: <HomeRoute /> },
      { path: '/about-us', element: <AboutUs /> },
      { path: '/product', element: <Product /> },
      { path: '/pricing', element: <Pricing /> },
      { path: '/login', element: <LoginPage /> },
      { path: '/signup', element: <SignupPage /> },
      { path: '/forgot-password', element: <ForgotPasswordPage /> },
      { path: '/reset-password', element: <ResetPasswordPage /> },
    ],
  },
  {
    element: <PublicLayout />,
    children: [
      { path: '/verify-email', element: <VerifyEmailPage /> },
    ],
  },
  {
    element: <MinimalLayout />,
    children: [
      {
        path: '/verify-email-pending',
        element: (
          <ProtectedRoute>
            <EmailVerificationNotice />
          </ProtectedRoute>
        ),
      },
      {
        path: '/payment-success',
        element: (
          <ProtectedRoute>
            <PaymentSuccess />
          </ProtectedRoute>
        ),
      },
      {
        path: '/payment-cancel',
        element: (
          <ProtectedRoute>
            <PaymentCancel />
          </ProtectedRoute>
        ),
      },
    ],
  },
  {
    path: '/try-finsight',
    element: <TryAskFinSight />,
  },
  {
    path: '/onboarding',
    element: (
      <ProtectedRoute>
        <UserOnboarding />
      </ProtectedRoute>
    ),
  },
  {
    element: (
      <ProtectedRoute>
        <ProtectedRouteLayout />
      </ProtectedRoute>
    ),
    children: [
      { path: '/dashboard', element: <Dashboard /> },
      { path: '/market_insights', element: <MarketInsigts /> },
      { path: '/ask_finsight', element: <AskFinSight /> },
      { path: '/ask_finsight/c/:conversationId', element: <AskFinSight /> },
      { path: '/user_profile', element: <UserProfile /> },
      {
        path: '/admin',
        element: (
          <AdminRoute>
            <AdminDashboard />
          </AdminRoute>
        ),
      },
      {
        path: '/admin/scraping',
        element: (
          <AdminRoute>
            <AdminScrapingPage />
          </AdminRoute>
        ),
      },
      {
        path: '/admin/insights',
        element: (
          <AdminRoute>
            <AdminInsightsPage />
          </AdminRoute>
        ),
      },
      {
        path: '/admin/brokers',
        element: (
          <AdminRoute>
            <AdminBrokersPage />
          </AdminRoute>
        ),
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
];

const AppRoutes: FC = () => {
  const routes = useRoutes(routesConfig);

  return (
    <Suspense fallback={<Loader />}>
      {routes}
    </Suspense>
  );
};

export default AppRoutes;
