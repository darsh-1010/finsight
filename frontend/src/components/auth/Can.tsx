import React, { type ReactNode } from 'react';

import { useAuth } from '../../context/AuthContext';

type Entitlement = string | string[];

interface CanProps {
  /**
   * Single entitlement or multiple entitlements
   */
  entitlement: Entitlement;

  /**
   * "any" → at least one entitlement is required (default)
   * "all" → all entitlements are required
   */
  mode?: 'any' | 'all';

  children: ReactNode;
  fallback?: ReactNode;
}

export const Can: React.FC<CanProps> = ({
  entitlement,
  mode = 'any',
  children,
  fallback = null,
}) => {
  const { hasEntitlement, isLoading } = useAuth();

  if (isLoading) {
    return null; // or <Loader />
  }

  const entitlements = Array.isArray(entitlement)
    ? entitlement
    : [entitlement];

  const isAllowed =
    mode === 'all'
      ? entitlements.every(hasEntitlement)
      : entitlements.some(hasEntitlement);

  if (!isAllowed) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
};

export default Can;
