'use client';

import React, { useEffect } from 'react';
import NextLink from 'next/link';
import { usePathname, useRouter, useSearchParams as useNextSearchParams, useParams as useNextParams } from 'next/navigation';

export interface LinkProps extends Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> {
  to: string;
  replace?: boolean;
}

export const Link = React.forwardRef<HTMLAnchorElement, LinkProps>(({ to, replace, ...props }, ref) => {
  return <NextLink href={to} replace={replace} {...props} ref={ref} />;
});
Link.displayName = 'Link';

export interface NavLinkProps extends Omit<LinkProps, 'className'> {
  className?: string | ((props: { isActive: boolean }) => string);
  end?: boolean;
}

export const NavLink = React.forwardRef<HTMLAnchorElement, NavLinkProps>(
  ({ to, className, end, ...props }, ref) => {
    const pathname = usePathname();
    const isActive = end ? pathname === to : pathname.startsWith(to);

    const resolvedClassName = typeof className === 'function' ? className({ isActive }) : className;

    return <NextLink href={to} className={resolvedClassName} {...props} ref={ref} />;
  }
);
NavLink.displayName = 'NavLink';

export function useNavigate() {
  const router = useRouter();
  return (to: string | number, options?: { replace?: boolean; state?: any }) => {
    if (typeof to === 'number') {
      if (to === -1) {
        router.back();
      } else if (to === 1) {
        router.forward();
      }
    } else {
      if (options?.replace) {
        router.replace(to);
      } else {
        router.push(to);
      }
    }
  };
}

export function useLocation() {
  const pathname = usePathname();
  const searchParams = useNextSearchParams();
  const searchString = searchParams.toString();
  return {
    pathname,
    search: searchString ? `?${searchString}` : '',
    hash: '',
    state: null,
  };
}

export function useParams() {
  return useNextParams();
}

export function useSearchParams(): [URLSearchParams, (nextInit: any) => void] {
  const searchParams = useNextSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const setSearchParams = (nextInit: any) => {
    const newParams = new URLSearchParams(nextInit);
    router.push(`${pathname}?${newParams.toString()}`);
  };

  return [searchParams, setSearchParams];
}

export interface NavigateProps {
  to: string;
  replace?: boolean;
}

export function Navigate({ to, replace }: NavigateProps) {
  const router = useRouter();
  useEffect(() => {
    if (replace) {
      router.replace(to);
    } else {
      router.push(to);
    }
  }, [to, replace, router]);
  return null;
}
