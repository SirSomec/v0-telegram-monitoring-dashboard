/** @type {import('next').NextConfig} */
const apiTarget =
  process.env.API_PROXY_TARGET || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"

const nextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // Проксирование на бэкенд при пустом NEXT_PUBLIC_API_URL (только http(s); WebSocket — через NEXT_PUBLIC_API_URL на клиенте)
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiTarget}/api/:path*` },
      { source: "/auth/:path*", destination: `${apiTarget}/auth/:path*` },
      { source: "/docs", destination: `${apiTarget}/docs` },
      { source: "/openapi.json", destination: `${apiTarget}/openapi.json` },
    ]
  },
}

export default nextConfig
