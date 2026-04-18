import type { Metadata } from 'next'
import { Space_Grotesk, JetBrains_Mono } from 'next/font/google'
import './globals.css'

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-space-grotesk',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
})

export const metadata: Metadata = {
  title: '미션컨트롤 — 투자 인텔리전스',
  description: '기관급 금융 인텔리전스 대시보드',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko" className={`${spaceGrotesk.variable} ${jetbrainsMono.variable}`}>
      <body className="bg-mc-bg text-foreground font-sans antialiased">
        {children}
      </body>
    </html>
  )
}
