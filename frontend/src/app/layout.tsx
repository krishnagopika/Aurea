import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Aurea — AI-Powered Property Risk Intelligence',
  description:
    'Instant underwriting decisions backed by real planning, flood, and environmental data. Powered by 6 specialist AI agents.',
  keywords: ['insurance', 'underwriting', 'property risk', 'AI', 'UK property', 'fintech'],
  openGraph: {
    title: 'Aurea — AI-Powered Property Risk Intelligence',
    description:
      'Instant underwriting decisions backed by real planning, flood, and environmental data.',
    type: 'website',
  },
}

export const viewport: Viewport = {
  themeColor: '#2563EB',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-slate-50 text-slate-700 antialiased font-sans">
        {children}
      </body>
    </html>
  )
}
