'use client'

import { motion } from 'framer-motion'
import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

type Decision = 'ACCEPT' | 'REFER' | 'DECLINE'

interface DecisionBadgeProps {
  decision: Decision
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const decisionConfig = {
  ACCEPT: {
    label: 'Accepted',
    Icon: CheckCircle,
    textClass: 'text-emerald-700',
    bgClass: 'bg-emerald-50',
    borderClass: 'border-emerald-200',
    dotClass: 'bg-emerald-500',
  },
  REFER: {
    label: 'Referred',
    Icon: AlertTriangle,
    textClass: 'text-amber-700',
    bgClass: 'bg-amber-50',
    borderClass: 'border-amber-200',
    dotClass: 'bg-amber-500',
  },
  DECLINE: {
    label: 'Declined',
    Icon: XCircle,
    textClass: 'text-red-700',
    bgClass: 'bg-red-50',
    borderClass: 'border-red-200',
    dotClass: 'bg-red-500',
  },
} as const

const sizeConfig = {
  sm: {
    badge: 'px-3 py-1 text-xs gap-1.5 rounded-full',
    icon: 'h-3.5 w-3.5',
    dot: 'h-1.5 w-1.5',
  },
  md: {
    badge: 'px-5 py-2 text-sm gap-2 rounded-full',
    icon: 'h-4 w-4',
    dot: 'h-2 w-2',
  },
  lg: {
    badge: 'px-8 py-3.5 text-xl gap-3 rounded-2xl',
    icon: 'h-6 w-6',
    dot: 'h-2.5 w-2.5',
  },
}

export default function DecisionBadge({
  decision,
  size = 'md',
  className,
}: DecisionBadgeProps) {
  const cfg = decisionConfig[decision]
  const sz = sizeConfig[size]
  const { Icon } = cfg

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.7, y: -6 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 450, damping: 24 }}
      className={cn(
        'inline-flex items-center border font-semibold tracking-wide uppercase select-none',
        cfg.bgClass,
        cfg.borderClass,
        cfg.textClass,
        sz.badge,
        className,
      )}
    >
      {/* Pulsing live dot */}
      <span className="relative flex shrink-0 items-center justify-center">
        <span
          className={cn(
            'animate-ping absolute inline-flex rounded-full opacity-60',
            cfg.dotClass,
            sz.dot,
          )}
        />
        <span
          className={cn('relative inline-flex rounded-full', cfg.dotClass, sz.dot)}
        />
      </span>

      <Icon className={cn('shrink-0', sz.icon)} aria-hidden="true" strokeWidth={2} />
      <span>{cfg.label}</span>
    </motion.div>
  )
}
