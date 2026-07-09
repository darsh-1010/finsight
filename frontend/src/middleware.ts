import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Edge middleware — fast auth check using the session cookie.
 * Redirects unauthenticated users away from protected routes.
 *
 * Note: Auth state is managed client-side (JWT/session cookie).
 * The server-side check here is lightweight — full auth validation
 * happens client-side in the ProtectedGroupLayout.
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check for any auth cookie set by the backend
  const hasSession =
    request.cookies.has('access_token') ||
    request.cookies.has('session') ||
    request.cookies.has('auth_token') ||
    request.cookies.has('csrftoken');

  const isProtectedRoute =
    pathname.startsWith('/dashboard') ||
    pathname.startsWith('/market_insights') ||
    pathname.startsWith('/ask_finsight') ||
    pathname.startsWith('/user_profile') ||
    pathname.startsWith('/sandbox') ||
    pathname.startsWith('/admin');

  // Only redirect if definitely unauthenticated (no cookies at all)
  // The client-side layout handles full validation
  if (isProtectedRoute && !hasSession) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/market_insights/:path*',
    '/ask_finsight/:path*',
    '/user_profile/:path*',
    '/sandbox/:path*',
    '/admin/:path*',
  ],
};
