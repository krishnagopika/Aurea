'use client'

import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

interface RiskScoreRingProps {
  score: number
  label?: string
  size?: number
  strokeWidth?: number
  className?: string
}

function getScoreColor(score: number): string {
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

export default function RiskScoreRing({
  score,
  label = 'Risk Score',
  size = 148,
  strokeWidth = 10,
  className,
}: RiskScoreRingProps) {
  const [animatedScore, setAnimatedScore] = useState(0)
  const [dashOffset, setDashOffset] = useState(0)
  const rafRef = useRef<number | null>(null)

  const clampedScore = Math.min(100, Math.max(0, score))
  const color = getScoreColor(clampedScore)
  const center = size / 2
  const radius = center - strokeWidth / 2 - 2
  const circumference = 2 * Math.PI * radius

  useEffect(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)

    const duration = 1600
    const startTime = performance.now()

    const animate = (now: number) => {
      const elapsed = now - startTime
      const raw = Math.min(elapsed / duration, 1)
      // Ease-out cubic
      const t = 1 - Math.pow(1 - raw, 3)

      const currentScore = Math.round(t * clampedScore)
      const currentOffset = circumference - (t * clampedScore / 100) * circumference

      setAnimatedScore(currentScore)
      setDashOffset(currentOffset)

      if (raw < 1) {
        rafRef.current = requestAnimationFrame(animate)
      }
    }

    rafRef.current = requestAnimationFrame(animate)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [clampedScore, circumference])

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.15, duration: 0.5, type: 'spring', stiffness: 300 }}
      className={`relative inline-flex items-center justify-center ${className ?? ''}`}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="-rotate-90"
        aria-label={`Risk score: ${clampedScore} out of 100`}
        role="img"
      >
        {/* Track — slate-200 in light mode */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#E2E8F0"
          strokeWidth={strokeWidth}
        />

        {/* Gradient definition */}
        <defs>
          <linearGradient id="ring-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="1" />
            <stop offset="100%" stopColor={color} stopOpacity="0.7" />
          </linearGradient>
        </defs>

        {/* Animated progress arc */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="url(#ring-gradient)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
        />
      </svg>

      {/* Center label */}
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span
          className="text-3xl font-black tabular-nums leading-none"
          style={{ color }}
        >
          {animatedScore}
        </span>
        <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-widest mt-1">
          {label}
        </span>
        <span className="text-xs mt-0.5" style={{ color }}>
          {getRiskLabel(clampedScore)}
        </span>
      </div>
    </motion.div>
  )
}
