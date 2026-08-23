import { usePathname, useRouter, useSearchParams } from 'next/navigation';

type SearchParamsInit = Record<string, string> | ((prev: URLSearchParams) => URLSearchParams);

/**
 * Update the query string on the current path. Mirrors the react-router-dom
 * `useSearchParams()` setter this app relied on (accepts either a plain object
 * or a `(prev) => URLSearchParams` updater), since next/navigation's
 * `useSearchParams()` is read-only.
 */
export function useUpdateSearchParams() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  return (init: SearchParamsInit, options?: { replace?: boolean }) => {
    const next = typeof init === 'function' ? init(new URLSearchParams(searchParams)) : new URLSearchParams(init);
    const query = next.toString();
    const url = query ? `${pathname}?${query}` : pathname;

    if (options?.replace) {
      router.replace(url);
    } else {
      router.push(url);
    }
  };
}

export { useSearchParams };
