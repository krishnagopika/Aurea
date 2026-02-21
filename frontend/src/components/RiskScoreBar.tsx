'use client'

import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

interface RiskScoreBarProps {
  label: string
  score: number
  weight?: number
  delay?: number
  className?: string
}

function getBarColor(score: number): string {
  if (score <= 33) return '#10B981'
  if (score <= 66) return '#F59E0B'
  return '#EF4444'
}

function getRiskLabel(score: number): string {
  if (score <= 20) return 'Very Low'
  if (score <= 40) return 'Low'
  if (score <= 60) return 'Moderate'
  if (score <= 80) return 'High'
  return 'Very High'
}

export default function RiskScoreBar({
  label,
  score,
  weight,
  delay = 0,
  className,
}: RiskScoreBarProps) {
  const [animatedWidth, setAnimatedWidth] = useState(0)
  const [animatedScore, setAnimatedScore] = useState(0)
  const rafRef = useRef<number | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clampedScore = Math.min(100, Math.max(0, score))
  const color = getBarColor(clampedScore)

  useEffect(() => {
    timerRef.current = setTimeout(() => {
      const duration = 1200
      const startTime = performance.now()

      const animate = (now: number) => {
        const elapsed = now - startTime
        const raw = Math.min(elapsed / duration, 1)
        const t = 1 - Math.pow(1 - raw, 3)

        setAnimatedWidth(t * clampedScore)
        setAnimatedScore(Math.round(t * clampedScore))

        if (raw < 1) {
          rafRef.current = requestAnimationFrame(animate)
        }
      }

      rafRef.current = requestAnimationFrame(animate)
    }, delay)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [clampedScore, delay])

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: delay / 1000, duration: 0.4 }}
      className={`space-y-2 ${className ?? ''}`}
    >
      {/* Header row */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-medium text-slate-700 truncate">{label}</span>
          {weight !== undefined && (
            <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-mono text-slate-500">
              {weight}%
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-3">
          <span className="text-xs font-medium" style={{ color }}>
            {getRiskLabel(clampedScore)}
          </span>
          <span className="font-bold tabular-nums" style={{ color }}>
            {animatedScore}
            <span className="text-slate-400 font-normal text-xs">/100</span>
          </span>
        </div>
      </div>

      {/* Bar track — slate-200 */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full"
          style={{
            width: `${animatedWidth}%`,
            backgroundColor: color,
            transition: 'none',
          }}
        />
      </div>
    </motion.div>
  )
}
