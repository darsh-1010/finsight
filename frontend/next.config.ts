import path from 'path';
import { fileURLToPath } from 'url';
import type { NextConfig } from 'next';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const nextConfig: NextConfig = {
  // Enable standalone output for Docker deployment
  output: 'standalone',

  // Disable x-powered-by header for security
  poweredByHeader: false,

  // Allow images from any source (for TradingView, etc.)
  images: {
    unoptimized: true,
  },

  // Ignore ESLint and TS build checks during production build
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },

  webpack: (config, { webpack }) => {
    config.resolve.alias['react-router-dom'] = path.resolve(__dirname, 'src/lib/react-router-dom-shim.tsx');
    config.plugins.push(
      new webpack.DefinePlugin({
        'import.meta.env.VITE_API_BASE_URL': JSON.stringify(process.env.VITE_API_BASE_URL || ''),
        'import.meta.env.VITE_VISITING_USER_COOKIE_NAME': JSON.stringify(process.env.VITE_VISITING_USER_COOKIE_NAME || ''),
      })
    );
    return config;
  },
};

export default nextConfig;
