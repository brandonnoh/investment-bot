import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  images: { unoptimized: true },
  async headers() {
    return [
      {
        // HTML 페이지는 캐시 안 함 → 항상 최신 청크 URL 사용
        source: '/',
        headers: [{ key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate' }],
      },
      {
        // JS/CSS 청크는 파일명에 해시 포함 → 영구 캐시 OK
        source: '/_next/static/:path*',
        headers: [{ key: 'Cache-Control', value: 'public, max-age=31536000, immutable' }],
      },
    ]
  },
}

export default nextConfig
