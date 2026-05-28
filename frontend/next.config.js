/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  // Proxy API calls to backend so the frontend only talks to itself
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8086/api/v1/:path*",
      },
    ];
  },
};

module.exports = nextConfig;