import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  images: { unoptimized: true },
  poweredByHeader: false,
  async headers() {
    return [
      {
        // 모든 경로에 보안 헤더 적용
        source: '/(.*)',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://s3.tradingview.com",
              "style-src 'self' 'unsafe-inline' https://s3.tradingview.com",
              "img-src 'self' data: blob: https://*.tradingview.com https://*.tv-cdn.net",
              "frame-src 'self' https://*.tradingview.com https://*.tv-cdn.net",
              "connect-src 'self' https://*.tradingview.com",
              "font-src 'self' data: https://s3.tradingview.com",
            ].join('; '),
          },
        ],
      },
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
