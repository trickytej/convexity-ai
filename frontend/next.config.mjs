/** @type {import('next').NextConfig} */
const nextConfig = {
  // API base for server-side fetches; overridable in deployment.
  env: {
    API_BASE_URL: process.env.API_BASE_URL ?? "http://127.0.0.1:8000",
  },
};

export default nextConfig;
