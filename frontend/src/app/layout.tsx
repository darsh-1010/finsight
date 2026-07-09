import type { Metadata } from 'next';
import { Providers } from './providers';
import './globals.css';

export const metadata: Metadata = {
  title: 'FinSight — AI-Powered Financial Intelligence',
  description:
    'FinSight brings clarity, structure, and professional thinking to investing. Experience institutional-grade financial research powered by AI.',
  keywords: ['financial intelligence', 'AI investing', 'market insights', 'portfolio analysis'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
