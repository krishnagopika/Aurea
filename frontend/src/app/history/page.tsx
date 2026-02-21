'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Loader2,
  AlertCircle,
  MapPin,
  Calendar,
  TrendingUp,
  AlertTriangle,
  ArrowUpDown,
  BarChart2,
} from 'lucide-react'
import Navbar from '@/components/Navbar'
import DecisionBadge from '@/components/DecisionBadge'
import RiskScoreBar from '@/components/RiskScoreBar'
import { Button } from '@/components/ui/button'
import { getHistory, type HistoryItem, ApiError } from '@/lib/api'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function scoreColorClass(score: number): string {
  if (score <= 33) return 'text-emerald-600'
  if (score <= 66) return 'text-amber-600'
  return 'text-red-600'
}

type SortKey = 'date' | 'score' | 'decision'
type SortDir = 'asc' | 'desc'

function sortHistory(items: HistoryItem[], key: SortKey, dir: SortDir): HistoryItem[] {
  return [...items].sort((a, b) => {
    let cmp = 0
    if (key === 'date') {
      cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    } else if (key === 'score') {
      cmp = a.risk_scores.overall_risk_score - b.risk_scores.overall_risk_score
    } else if (key === 'decision') {
      const order: Record<string, number> = { ACCEPT: 0, REFER: 1, DECLINE: 2 }
      cmp = (order[a.decision] ?? 0) - (order[b.decision] ?? 0)
    }
    return dir === 'asc' ? cmp : -cmp
  })
}

// ─── Row component ────────────────────────────────────────────────────────────

function HistoryRow({ item, index }: { item: HistoryItem; index: number }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <motion.div
      key={item.id}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.35 }}
      className="border-b border-slate-100 last:border-0"
    >
      {/* Summary row */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left group"
        aria-expanded={expanded}
        aria-controls={`row-${item.id}`}
      >
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto_auto_auto] gap-3 sm:gap-4 px-5 py-4 hover:bg-slate-50 transition-colors duration-150 rounded-xl">
          {/* Address */}
          <div className="flex items-center gap-2.5 min-w-0">
            <MapPin className="h-3.5 w-3.5 text-blue-600 shrink-0" aria-hidden="true" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-900 truncate">{item.address}</p>
              <p className="text-xs text-slate-500 font-mono">{item.postcode}</p>
            </div>
          </div>

          {/* Decision */}
          <div className="flex items-center">
            <DecisionBadge decision={item.decision} size="sm" />
          </div>

          {/* Risk score */}
          <div className="flex items-center">
            <span className={`text-sm font-bold tabular-nums ${scoreColorClass(item.risk_scores.overall_risk_score)}`}>
              {item.risk_scores.overall_risk_score}
              <span className="text-slate-400 font-normal text-xs">/100</span>
            </span>
          </div>

          {/* Premium */}
          <div className="flex items-center">
            <span className="text-sm font-bold text-slate-900 tabular-nums">
              {item.premium_multiplier.toFixed(2)}
              <span className="text-blue-600 text-xs">&times;</span>
            </span>
          </div>

          {/* Date + chevron */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">{formatDate(item.created_at)}</span>
            <div className="text-slate-400 group-hover:text-slate-600 transition-colors">
              {expanded ? (
                <ChevronUp className="h-4 w-4" aria-hidden="true" />
              ) : (
                <ChevronDown className="h-4 w-4" aria-hidden="true" />
              )}
            </div>
          </div>
        </div>
      </button>

      {/* Expanded details */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            id={`row-${item.id}`}
            key="detail"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.28, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-6 pt-4 border-t border-slate-200 bg-slate-50 rounded-b-xl">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Risk breakdown */}
                <div className="space-y-4">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                    Risk Breakdown
                  </h4>
                  <RiskScoreBar
                    label="Flood Risk"
                    score={item.risk_scores.flood_risk_score}
                    weight={45}
                    delay={0}
                  />
                  <RiskScoreBar
                    label="Property Age Risk"
                    score={item.risk_scores.property_age_risk_score}
                    weight={30}
                    delay={120}
                  />
                  <RiskScoreBar
                    label="Planning & Development Risk"
                    score={item.risk_scores.planning_development_risk_score}
                    weight={25}
                    delay={240}
                  />
                </div>

                {/* Narrative */}
                <div>
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">
                    Decision Narrative
                  </h4>
                  <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
                    <p className="text-sm text-slate-700 leading-relaxed">
                      {item.plain_english_narrative}
                    </p>
                  </div>
                </div>
              </div>

              {/* Policy citations */}
              {item.policy_citations && item.policy_citations.length > 0 && (
                <div className="mt-5">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">
                    Policy Citations
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {item.policy_citations.map((c, i) => (
                      <span
                        key={i}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Warnings */}
              {item.data_warnings && item.data_warnings.length > 0 && (
                <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-600" aria-hidden="true" />
                    <span className="text-xs font-semibold text-amber-700">Data Warnings</span>
                  </div>
                  <ul className="space-y-1.5">
                    {item.data_warnings.map((w, i) => (
                      <li key={i} className="text-xs text-amber-700 flex items-start gap-2">
                        <span className="text-amber-400 mt-0.5">•</span>
                        {w}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HistoryPage() {
  const router = useRouter()
  const [token, setToken] = useState<string | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  useEffect(() => {
    const t = localStorage.getItem('aurea_token')
    if (!t) {
      router.replace('/login')
      return
    }
    setToken(t)

    const fetchHistory = async () => {
      try {
        const data = await getHistory(t)
        setHistory(Array.isArray(data) ? data : [])
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 401) {
            localStorage.removeItem('aurea_token')
            router.replace('/login')
            return
          }
          setError(err.message)
        } else {
          setError('Failed to load history. Please try again.')
        }
      } finally {
        setLoading(false)
      }
    }

    fetchHistory()
  }, [router])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sorted = sortHistory(history, sortKey, sortDir)

  const stats = [
    { label: 'Total', value: history.length, colorClass: 'text-slate-900' },
    { label: 'Accepted', value: history.filter((h) => h.decision === 'ACCEPT').length, colorClass: 'text-emerald-600' },
    { label: 'Referred', value: history.filter((h) => h.decision === 'REFER').length, colorClass: 'text-amber-600' },
    { label: 'Declined', value: history.filter((h) => h.decision === 'DECLINE').length, colorClass: 'text-red-600' },
  ]

  if (!token) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" aria-label="Loading..." />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="mb-8 flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
              <ClipboardList className="h-5 w-5 text-blue-600" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Assessment History</h1>
              <p className="text-sm text-slate-500">All previous property risk assessments</p>
            </div>
          </div>

          <Link href="/assess">
            <Button variant="primary" size="md">
              <BarChart2 className="h-4 w-4" aria-hidden="true" />
              New Assessment
            </Button>
          </Link>
        </motion.div>

        {/* Loading */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="relative">
              <div className="h-12 w-12 rounded-full border-2 border-slate-200" />
              <div className="absolute inset-0 h-12 w-12 rounded-full border-t-2 border-blue-600 animate-spin" />
            </div>
            <p className="text-sm text-slate-500">Loading history...</p>
          </div>
        )}

        {/* Error */}
        {error && !loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-5"
          >
            <AlertCircle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <p className="text-sm font-medium text-red-700">{error}</p>
              <button
                onClick={() => window.location.reload()}
                className="mt-2 text-xs text-red-600 hover:text-red-700 underline"
              >
                Try again
              </button>
            </div>
          </motion.div>
        )}

        {/* Empty state */}
        {!loading && !error && history.length === 0 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
            className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-24 text-center"
          >
            <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-400">
              <ClipboardList className="h-7 w-7" aria-hidden="true" />
            </div>
            <p className="text-slate-700 font-semibold mb-2">No assessments yet</p>
            <p className="text-sm text-slate-400 mb-8 max-w-xs leading-relaxed">
              Run your first property assessment to see results here
            </p>
            <Link href="/assess">
              <Button variant="primary" size="md">
                Run Your First Assessment
              </Button>
            </Link>
          </motion.div>
        )}

        {/* Stats row */}
        {!loading && !error && history.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}
            className="mb-6 grid grid-cols-2 sm:grid-cols-4 gap-3"
          >
            {stats.map(({ label, value, colorClass }) => (
              <div
                key={label}
                className="rounded-xl bg-white border border-slate-200 shadow-sm p-4 text-center"
              >
                <p className={`text-2xl font-black tabular-nums ${colorClass}`}>{value}</p>
                <p className="text-xs text-slate-500 mt-1">{label}</p>
              </div>
            ))}
          </motion.div>
        )}

        {/* History table */}
        {!loading && !error && history.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15, duration: 0.45 }}
            className="rounded-2xl bg-white border border-slate-200 shadow-sm overflow-hidden"
          >
            {/* Table header with sort buttons */}
            <div className="hidden sm:grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 px-5 py-3 border-b border-slate-200 bg-slate-50">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Address</span>

              {(['decision', 'score', 'premium', 'date'] as const).map((col) => {
                const key = col === 'score' ? 'score' : col === 'decision' ? 'decision' : 'date'
                const label = { decision: 'Decision', score: 'Risk Score', premium: 'Premium', date: 'Date' }[col]
                const isActive = sortKey === key && col !== 'premium'
                return (
                  <button
                    key={col}
                    type="button"
                    onClick={() => col !== 'premium' ? handleSort(key as SortKey) : undefined}
                    className={`flex items-center gap-1 text-xs font-semibold uppercase tracking-widest transition-colors ${
                      isActive ? 'text-blue-600' : 'text-slate-500 hover:text-slate-700'
                    } ${col === 'premium' ? 'cursor-default' : 'cursor-pointer'}`}
                  >
                    {label}
                    {col !== 'premium' && (
                      <ArrowUpDown className="h-3 w-3" aria-hidden="true" />
                    )}
                  </button>
                )
              })}
            </div>

            {/* Rows */}
            <div className="divide-y divide-slate-100">
              {sorted.map((item, index) => (
                <HistoryRow key={item.id} item={item} index={index} />
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
