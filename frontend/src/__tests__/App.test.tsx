import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import App from '../App';
import { ThemeProvider } from '../context/ThemeContext';

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});

describe('App', () => {
  it('renders without crashing', () => {
    render(
      <ThemeProvider>
        <App />
      </ThemeProvider>
    );
    // Just a smoke test for now, checking if it renders
    expect(document.body).toBeInTheDocument();
  });
});
