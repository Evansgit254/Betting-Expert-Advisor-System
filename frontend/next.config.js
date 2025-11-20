/**** @type {import('next').NextConfig} ****/
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    appDir: true,
  },
  output: 'standalone',
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5000',
  },
};

module.exports = nextConfig;
