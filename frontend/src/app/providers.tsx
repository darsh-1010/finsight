'use client';

import React from 'react';
import { Provider } from 'react-redux';
import { AuthProvider } from '@/context/AuthContext';
import { AlertProvider } from '@/context/AlertContext';
import { ThemeProvider } from '@/context/ThemeContext';
import { GlobalWebSocket } from '@/components/GlobalWebSocket';
import { store } from '@/store/store';

/**
 * Wraps the entire app with all client-side providers.
 * Must be "use client" since all providers use React hooks.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <Provider store={store}>
      <ThemeProvider>
        <AuthProvider>
          <AlertProvider>
            <GlobalWebSocket />
            {children}
          </AlertProvider>
        </AuthProvider>
      </ThemeProvider>
    </Provider>
  );
}
