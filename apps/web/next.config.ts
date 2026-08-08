import type { NextConfig } from 'next';

const apiInternalUrl = process.env.API_INTERNAL_URL || 'http://localhost:8000/api';

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${apiInternalUrl}/:path*` }];
  },
};

export default nextConfig;
