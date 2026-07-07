import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react';

import {
  authApi,
  clearVisitingUser,
  type User,
  type LoginCredentials,
  type SignupCredentials,
} from '../api/auth';
import { apiSlice } from '../store/apiSlice';
import { useAppDispatch } from '../store/hooks';

interface AuthContextType {
  isLoggedIn: boolean;
  user: User | null;
  isLoading: boolean;
  login: (data: LoginCredentials) => Promise<void>;
  signup: (data: SignupCredentials) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  updateUser: () => Promise<void>;
  hasEntitlement: (code: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const useAuthState = () => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      const userData = await authApi.getCurrentUser();

      setUser(userData);
      setIsLoggedIn(true);
    } catch {
      setUser(null);
      setIsLoggedIn(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    isLoggedIn,
    setIsLoggedIn,
    user,
    setUser,
    isLoading,
    setIsLoading,
    checkAuth,
  };
};

const useAuthActions = (
  checkAuth: () => Promise<void>,
  setUser: (user: User | null) => void,
  setIsLoggedIn: (isLoggedIn: boolean) => void,
  user: User | null
) => {
  const dispatch = useAppDispatch();

  const updateUser = useCallback(async () => {
    try {
      const userData = await authApi.getCurrentUser();
      console.log(userData)

      setUser(userData);
      setIsLoggedIn(true);
    } catch (e) {
      console.error('Failed to update user context:', e);
    }
  }, [setUser, setIsLoggedIn]);

  const login = useCallback(
    async (d: LoginCredentials) => {
      dispatch(apiSlice.util.resetApiState());
      return performAuthAction(async () => {
        await authApi.login(d);
        clearVisitingUser();
      }, checkAuth);
    },
    [checkAuth, dispatch]
  );

  const signup = useCallback(
    async (d: SignupCredentials) => {
      dispatch(apiSlice.util.resetApiState());
      return performAuthAction(async () => {
        await authApi.signup(d);
        clearVisitingUser();
      }, checkAuth);
    },
    [checkAuth, dispatch]
  );

  const logout = useCallback(
    async () => {
      await terminateSession(setUser, setIsLoggedIn);
      dispatch(apiSlice.util.resetApiState());
    },
    [setUser, setIsLoggedIn, dispatch]
  );

  const hasEntitlement = useCallback(
    (code: string): boolean => user?.entitlements?.includes(code) || false,
    [user]
  );

  const actions = useMemo(
    () => ({
      updateUser,
      login,
      signup,
      logout,
      hasEntitlement,
    }),
    [updateUser, login, signup, logout, hasEntitlement]
  );

  return actions;
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const {
    isLoggedIn,
    setIsLoggedIn,
    user,
    setUser,
    isLoading,
    checkAuth,
  } = useAuthState();

  const actions = useAuthActions(
    checkAuth,
    setUser,
    setIsLoggedIn,
    user
  );

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const contextValue = useMemo(
    () => ({
      isLoggedIn,
      user,
      isLoading,
      checkAuth,
      ...actions,
    }),
    [isLoggedIn, user, isLoading, checkAuth, actions]
  );

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

const performAuthAction = async (
  action: () => Promise<unknown>,
  onSuccess: () => Promise<void>
) => {
  await action();
  await onSuccess();
};

const terminateSession = async (
  setUser: (user: User | null) => void,
  setIsLoggedIn: (isLoggedIn: boolean) => void
) => {
  try {
    await authApi.logout();
  } finally {
    setUser(null);
    setIsLoggedIn(false);
  }
};

export const useAuth = () => {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
};