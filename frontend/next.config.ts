import type { NextConfig } from 'next';

// Runtime allowlisted API routes keep sandbox credentials on the server.
const nextConfig: NextConfig = { output: 'standalone' };
export default nextConfig;
