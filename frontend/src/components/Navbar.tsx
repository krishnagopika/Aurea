'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { ShieldCheck, LogOut, BarChart2, ClipboardList, Menu, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function Navbar() {
  const pathname = usePathname()
  const router = useRouter()
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  // Detect auth state from localStorage
  useEffect(() => {
    const check = () => setIsLoggedIn(!!localStorage.getItem('aurea_token'))
    check()
    window.addEventListener('storage', check)
    return () => window.removeEventListener('storage', check)
  }, [])

  const handleSignOut = () => {
    localStorage.removeItem('aurea_token')
    setIsLoggedIn(false)
    router.push('/')
  }

  const isActive = (path: string) => pathname === path

  const navLinks = isLoggedIn
    ? [
        { href: '/assess', label: 'Assess', Icon: BarChart2 },
        { href: '/history', label: 'History', Icon: ClipboardList },
      ]
    : []

  return (
    <motion.nav
      initial={{ y: -64, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="sticky top-0 z-50 w-full bg-white border-b border-slate-200 shadow-sm"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between gap-4">
          {/* Logo */}
          <Link
            href="/"
            className="flex items-center gap-2.5 shrink-0 group"
            aria-label="Aurea home"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 shadow-sm group-hover:bg-blue-700 transition-colors duration-200">
              <ShieldCheck className="h-5 w-5 text-white" strokeWidth={2.5} aria-hidden="true" />
            </div>
            <span className="text-xl font-black tracking-tight text-slate-900">
              Aurea
            </span>
          </Link>

          {/* Desktop nav links */}
          {navLinks.length > 0 && (
            <div className="hidden sm:flex items-center gap-1">
              {navLinks.map(({ href, label, Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    'flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium transition-all duration-150',
                    isActive(href)
                      ? 'bg-blue-50 text-blue-600 font-medium'
                      : 'text-slate-600 hover:text-blue-600 hover:bg-slate-50',
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {label}
                </Link>
              ))}
            </div>
          )}

          {/* Right side actions */}
          <div className="flex items-center gap-2">
            {isLoggedIn ? (
              <button
                onClick={handleSignOut}
                className="flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-all duration-150"
                aria-label="Sign out"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
                <span className="hidden sm:inline">Sign Out</span>
              </button>
            ) : (
              <>
                <Link
                  href="/login"
                  className="hidden sm:flex items-center rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all duration-150"
                >
                  Sign In
                </Link>
                <Link
                  href="/register"
                  className="flex items-center rounded-lg bg-blue-600 hover:bg-blue-700 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all duration-200 active:scale-95"
                >
                  Get Started
                </Link>
              </>
            )}

            {/* Mobile hamburger */}
            {navLinks.length > 0 && (
              <button
                className="sm:hidden flex items-center justify-center h-9 w-9 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                onClick={() => setMobileOpen((o) => !o)}
                aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
                aria-expanded={mobileOpen}
              >
                {mobileOpen ? (
                  <X className="h-5 w-5" aria-hidden="true" />
                ) : (
                  <Menu className="h-5 w-5" aria-hidden="true" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && navLinks.length > 0 && (
          <motion.div
            key="mobile-menu"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="sm:hidden overflow-hidden border-t border-slate-200 bg-white"
          >
            <div className="px-4 py-3 space-y-1">
              {navLinks.map(({ href, label, Icon }) => (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    'flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-all',
                    isActive(href)
                      ? 'bg-blue-50 text-blue-600'
                      : 'text-slate-600 hover:text-blue-600 hover:bg-slate-50',
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {label}
                </Link>
              ))}
              {isLoggedIn && (
                <button
                  onClick={() => { setMobileOpen(false); handleSignOut() }}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-all"
                >
                  <LogOut className="h-4 w-4" aria-hidden="true" />
                  Sign Out
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  )
}
