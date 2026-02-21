'use client'

import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle,
  Loader2,
  Clock,
  Cpu,
  Droplets,
  Leaf,
  BookOpen,
  Brain,
  FileText,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export type AgentStatus = 'pending' | 'running' | 'complete'

export interface Agent {
  id: string
  name: string
  description: string
  status: AgentStatus
}

interface AgentPipelineStatusProps {
  agents: Agent[]
  className?: string
}

const agentMeta: Record<string, { Icon: React.ElementType; color: string }> = {
  PropertyValuationAgent: { Icon: Cpu, color: '#2563EB' },
  FloodRiskAgent: { Icon: Droplets, color: '#2563EB' },
  EnvironmentalDataAgent: { Icon: Leaf, color: '#10B981' },
  PolicyAgent: { Icon: BookOpen, color: '#7C3AED' },
  CoordinatorAgent: { Icon: Brain, color: '#EA580C' },
  ExplainabilityAgent: { Icon: FileText, color: '#2563EB' },
}

function StatusIcon({ status }: { status: AgentStatus }) {
  if (status === 'complete') {
    return (
      <motion.div
        initial={{ scale: 0, rotate: -90 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ type: 'spring', stiffness: 500, damping: 20 }}
      >
        <CheckCircle className="h-4 w-4 text-emerald-600 shrink-0" aria-hidden="true" />
      </motion.div>
    )
  }
  if (status === 'running') {
    return <Loader2 className="h-4 w-4 text-blue-600 shrink-0 animate-spin" aria-hidden="true" />
  }
  return <Clock className="h-4 w-4 text-slate-400 shrink-0" aria-hidden="true" />
}

export default function AgentPipelineStatus({
  agents,
  className,
}: AgentPipelineStatusProps) {
  const completedCount = agents.filter((a) => a.status === 'complete').length
  const runningCount = agents.filter((a) => a.status === 'running').length
  const totalCount = agents.length
  const progressPct = totalCount > 0 ? (completedCount / totalCount) * 100 : 0

  return (
    <div className={cn('rounded-xl bg-white border border-slate-200 p-5 space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
          Agent Pipeline
        </h3>
        <span className="text-xs text-slate-400 tabular-nums">
          {completedCount}/{totalCount}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
        <motion.div
          className="h-full rounded-full bg-blue-600"
          initial={{ width: 0 }}
          animate={{ width: `${progressPct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>

      {/* Agent list */}
      <div className="space-y-2">
        {agents.map((agent, index) => {
          const meta = agentMeta[agent.id]
          const Icon = meta?.Icon ?? Cpu
          const accentColor = meta?.color ?? '#2563EB'

          const isRunning = agent.status === 'running'
          const isDone = agent.status === 'complete'

          return (
            <motion.div
              key={agent.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.06, duration: 0.3 }}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 border transition-all duration-300',
                isRunning
                  ? 'bg-blue-50 border-blue-200'
                  : isDone
                    ? 'bg-white border-slate-100'
                    : 'bg-slate-50 border-slate-200',
              )}
            >
              {/* Agent icon */}
              <div
                className={cn(
                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-all duration-300',
                  isRunning
                    ? 'bg-blue-100'
                    : isDone
                      ? 'bg-emerald-50'
                      : 'bg-slate-200',
                )}
              >
                <Icon
                  className="h-4 w-4"
                  style={{
                    color: isDone ? '#10B981' : isRunning ? accentColor : '#94A3B8',
                  }}
                  aria-hidden="true"
                />
              </div>

              {/* Agent info */}
              <div className="flex-1 min-w-0">
                <p
                  className={cn(
                    'text-sm font-medium truncate transition-colors duration-300',
                    isRunning
                      ? 'text-blue-600'
                      : isDone
                        ? 'text-slate-900'
                        : 'text-slate-500',
                  )}
                >
                  {agent.name}
                </p>
                <p className="text-[11px] text-slate-400 truncate mt-0.5">
                  {agent.description}
                </p>
              </div>

              {/* Status */}
              <div className="shrink-0">
                <StatusIcon status={agent.status} />
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Running status message */}
      <AnimatePresence>
        {runningCount > 0 && (
          <motion.p
            key="running-msg"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="text-xs text-blue-600 text-center pb-1"
          >
            Agents are analysing your property...
          </motion.p>
        )}
        {completedCount === totalCount && totalCount > 0 && (
          <motion.p
            key="done-msg"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="text-xs text-emerald-600 text-center pb-1"
          >
            All agents completed successfully
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}
