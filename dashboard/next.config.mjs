/** @type {import('next').NextConfig} */
const API_ORIGIN = process.env.API_PROXY_ORIGIN || "";

const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  ...(API_ORIGIN
    ? {
        async rewrites() {
          return [
            {
              source: "/api/v1/:path*",
              destination: `${API_ORIGIN}/api/v1/:path*`,
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
