/** @type {import('next').NextConfig} */
export default {
  // The dev proxy cuts requests off after 30s by default, but a scan runs the agent and can take
  // a minute or more. Match Vercel's maxDuration for api/index.py (300s, see vercel.json).
  experimental: { proxyTimeout: 300_000 },
  // In dev, the Python API runs on :8000 (uvicorn). On Vercel, /api/* goes to api/index.py (see vercel.json).
  async rewrites() {
    return process.env.NODE_ENV === "development"
      ? [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }]
      : [];
  },
};
