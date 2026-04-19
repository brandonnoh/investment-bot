import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  images: { unoptimized: true },
  async rewrites() {
    const apiBase = process.env.PYTHON_API_URL ?? 'http://localhost:8421'
    return [
      { source: '/api/:path*', destination: `${apiBase}/api/:path*` },
    ]
  },
}

export default nextConfig
