'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'
import {
  ShieldCheck,
  ChevronRight,
  Zap,
  BarChart3,
  FileText,
  Cpu,
  Droplets,
  Leaf,
  BookOpen,
  Brain,
  ArrowRight,
  Activity,
  Globe,
  Clock,
} from 'lucide-react'
import Navbar from '@/components/Navbar'

// ─── Animation helpers ────────────────────────────────────────────────────────

/** Returns framer-motion animate props with a staggered delay */
function fadeUpProps(i: number = 0) {
  return {
    initial: { opacity: 0, y: 24 },
    animate: { opacity: 1, y: 0 },
    transition: { delay: i * 0.12, duration: 0.55, ease: 'easeOut' as const },
  }
}


// ─── Data ─────────────────────────────────────────────────────────────────────

const stats = [
  { value: '6', label: 'AI Agents', Icon: Activity },
  { value: '< 30s', label: 'Decisions', Icon: Clock },
  { value: 'Real UK', label: 'Data Sources', Icon: Globe },
]

const features = [
  {
    Icon: Zap,
    title: '6 Specialist AI Agents',
    desc: 'Valuation, flood risk, environmental data, policy retrieval, coordination, and explainability — orchestrated in real time.',
    color: '#2563EB',
    iconBg: '#EFF6FF',
  },
  {
    Icon: BarChart3,
    title: 'Real-Time Risk Scoring',
    desc: 'Live data from Environment Agency flood zones, IBEX planning data, and EPC property records for accurate risk profiles.',
    color: '#059669',
    iconBg: '#ECFDF5',
  },
  {
    Icon: FileText,
    title: 'Plain-English Decisions',
    desc: 'Every underwriting decision comes with a clear narrative explanation — no black boxes, full auditability.',
    color: '#7C3AED',
    iconBg: '#F5F3FF',
  },
]

const steps = [
  {
    step: '01',
    label: 'Enter Address',
    desc: 'Provide the property address and postcode to begin the automated assessment.',
    agent: 'PropertyValuationAgent fetches IBEX planning data',
  },
  {
    step: '02',
    label: 'AI Agents Analyse',
    desc: 'Six specialist agents run in parallel to assess every dimension of risk.',
    agent: 'FloodRiskAgent + EnvironmentalDataAgent + PolicyAgent',
  },
  {
    step: '03',
    label: 'Instant Decision',
    desc: 'Receive an ACCEPT, REFER, or DECLINE decision with full rationale in seconds.',
    agent: 'CoordinatorAgent + ExplainabilityAgent',
  },
]

const agents = [
  {
    Icon: Cpu,
    name: 'PropertyValuationAgent',
    desc: 'Fetches IBEX planning history, development activity, and property valuation data.',
    color: '#2563EB',
    iconBg: '#EFF6FF',
  },
  {
    Icon: Droplets,
    name: 'FloodRiskAgent',
    desc: 'Queries Environment Agency flood zone classifications and surface water risk.',
    color: '#0369A1',
    iconBg: '#F0F9FF',
  },
  {
    Icon: Leaf,
    name: 'EnvironmentalDataAgent',
    desc: 'Retrieves EPC energy performance certificates and environmental hazard data.',
    color: '#059669',
    iconBg: '#ECFDF5',
  },
  {
    Icon: BookOpen,
    name: 'PolicyAgent',
    desc: 'Searches MongoDB Atlas Vector Search for applicable underwriting policies.',
    color: '#7C3AED',
    iconBg: '#F5F3FF',
  },
  {
    Icon: Brain,
    name: 'CoordinatorAgent',
    desc: 'Aggregates all agent outputs to compute the final risk score and decision.',
    color: '#EA580C',
    iconBg: '#FFF7ED',
  },
  {
    Icon: ShieldCheck,
    name: 'ExplainabilityAgent',
    desc: 'Generates a plain-English narrative explaining the decision and risk factors.',
    color: '#2563EB',
    iconBg: '#EFF6FF',
  },
]

// ─── Component ────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white overflow-x-hidden">
      <Navbar />

      {/* ── HERO ─────────────────────────────────────────────────────────── */}
      <section className="relative flex min-h-[calc(100vh-64px)] flex-col items-center justify-center px-4 pt-16 pb-24 text-center overflow-hidden bg-gradient-to-b from-blue-50 to-white">
        <div className="relative z-10 flex flex-col items-center max-w-4xl mx-auto">
          {/* Badge */}
          <motion.div
            {...fadeUpProps(0)}
            className="mb-8 flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-1.5 text-xs font-semibold text-blue-700 tracking-wide uppercase"
          >
            <Activity className="h-3 w-3" aria-hidden="true" />
            Powered by AWS Bedrock &amp; MongoDB Atlas
          </motion.div>

          {/* Shield icon */}
          <motion.div
            {...fadeUpProps(1)}
            className="mb-8"
          >
            <div className="flex h-24 w-24 items-center justify-center rounded-3xl bg-blue-600 shadow-lg shadow-blue-200">
              <ShieldCheck className="h-12 w-12 text-white" strokeWidth={1.8} aria-hidden="true" />
            </div>
          </motion.div>

          {/* Wordmark */}
          <motion.h1
            {...fadeUpProps(2)}
            className="mb-2 text-6xl sm:text-7xl lg:text-8xl font-black tracking-tight leading-none text-slate-900"
          >
            <span className="text-gradient">Aurea</span>
          </motion.h1>

          {/* Tagline */}
          <motion.h2
            {...fadeUpProps(3)}
            className="mb-6 text-xl sm:text-2xl lg:text-3xl font-semibold text-slate-600"
          >
            AI-Powered Property Risk Intelligence
          </motion.h2>

          {/* Description */}
          <motion.p
            {...fadeUpProps(4)}
            className="mb-10 max-w-2xl text-base sm:text-lg text-slate-500 leading-relaxed"
          >
            Instant underwriting decisions backed by real planning, flood, and environmental
            data. Six specialist AI agents. One clear answer — in under 30 seconds.
          </motion.p>

          {/* CTA buttons */}
          <motion.div
            {...fadeUpProps(5)}
            className="flex flex-col sm:flex-row items-center gap-4"
          >
            <Link
              href="/register"
              className="group inline-flex items-center gap-2 rounded-xl bg-blue-600 px-8 py-4 text-base font-bold text-white shadow-sm hover:bg-blue-700 transition-all duration-200 active:scale-95"
            >
              Start Assessment
              <ChevronRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-8 py-4 text-base font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-all duration-200 active:scale-95"
            >
              Sign In
            </Link>
          </motion.div>
        </div>
      </section>

      {/* ── STATS BAR ─────────────────────────────────────────────────────── */}
      <section className="relative z-10 bg-blue-600 py-10 px-4">
        <div className="max-w-3xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="flex flex-wrap items-center justify-center gap-12 text-center"
          >
            {stats.map(({ value, label, Icon }, i) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1, duration: 0.4 }}
                className="flex flex-col items-center gap-1"
              >
                <Icon className="h-5 w-5 text-blue-200 mb-1" aria-hidden="true" />
                <span className="text-3xl font-black text-white">{value}</span>
                <span className="text-sm text-blue-200">{label}</span>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ── FEATURES ──────────────────────────────────────────────────────── */}
      <section className="relative z-10 py-24 px-4 bg-slate-50">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="text-center mb-14"
          >
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-3">
              Built for Modern Underwriting
            </h2>
            <p className="text-slate-500 max-w-xl mx-auto">
              Purpose-built AI agents replace manual data gathering with automated, auditable decisions.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            {features.map(({ Icon, title, desc, color, iconBg }, i) => (
              <motion.div
                key={title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.12, duration: 0.5 }}
                whileHover={{ y: -4, transition: { duration: 0.2 } }}
                className="group relative rounded-2xl bg-white border border-slate-200 p-6 hover:shadow-card-hover transition-all duration-300"
              >
                <div
                  className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl"
                  style={{ backgroundColor: iconBg }}
                >
                  <Icon className="h-6 w-6" style={{ color }} aria-hidden="true" />
                </div>
                <h3 className="mb-2 text-lg font-bold text-slate-900">{title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ──────────────────────────────────────────────────── */}
      <section className="relative py-24 px-4 bg-white">
        <div className="relative z-10 max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-3">How It Works</h2>
            <p className="text-slate-500">From address to decision in under 30 seconds</p>
          </motion.div>

          {/* Steps */}
          <div className="relative flex flex-col sm:flex-row items-stretch gap-0">
            {/* Connector lines (desktop) */}
            <div className="hidden sm:block absolute top-[2.5rem] left-0 right-0 h-px pointer-events-none">
              <div className="mx-auto max-w-[66%] h-full bg-gradient-to-r from-transparent via-blue-200 to-transparent" />
            </div>

            {steps.map(({ step, label, desc, agent }, i) => (
              <motion.div
                key={step}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.15, duration: 0.5 }}
                className="relative flex flex-1 flex-col items-center text-center px-6 py-8"
              >
                {/* Step number circle */}
                <div className="relative mb-5 flex h-14 w-14 items-center justify-center rounded-full border-2 border-blue-600 bg-blue-600 text-white font-black text-base z-10">
                  {step}
                </div>

                {/* Step content */}
                <h3 className="mb-2 text-lg font-bold text-slate-900">{label}</h3>
                <p className="mb-4 text-sm text-slate-500 leading-relaxed">{desc}</p>

                {/* Agent note */}
                <div className="rounded-lg bg-blue-50 border border-blue-100 px-3 py-2">
                  <p className="text-[11px] font-mono text-blue-600">{agent}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── AGENT SHOWCASE ────────────────────────────────────────────────── */}
      <section className="relative z-10 py-24 px-4 bg-slate-50">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="text-center mb-14"
          >
            <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 mb-3">
              Meet the Agent Team
            </h2>
            <p className="text-slate-500 max-w-xl mx-auto">
              Six purpose-built AI agents, each an expert in one domain of property risk.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map(({ Icon, name, desc, color, iconBg }, i) => (
              <motion.div
                key={name}
                initial={{ opacity: 0, scale: 0.95, y: 16 }}
                whileInView={{ opacity: 1, scale: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08, duration: 0.45 }}
                whileHover={{
                  y: -4,
                  transition: { duration: 0.22 },
                }}
                className="group relative rounded-xl bg-white border border-slate-200 p-5 cursor-default hover:shadow-card-hover transition-all duration-300"
              >
                <div className="flex items-start gap-4">
                  <div
                    className="shrink-0 flex h-11 w-11 items-center justify-center rounded-xl"
                    style={{ backgroundColor: iconBg }}
                  >
                    <Icon className="h-5 w-5" style={{ color }} aria-hidden="true" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-900 text-sm mb-1 font-mono">{name}</p>
                    <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* CTA */}
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="mt-12 text-center"
          >
            <Link
              href="/register"
              className="group inline-flex items-center gap-2 rounded-xl bg-blue-600 px-8 py-4 text-base font-bold text-white shadow-sm hover:bg-blue-700 transition-all duration-200 active:scale-95"
            >
              Try It Now — Free
              <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" aria-hidden="true" />
            </Link>
          </motion.div>
        </div>
      </section>

      {/* ── FOOTER ───────────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-200 bg-white py-10 px-4 text-center">
        <div className="flex items-center justify-center gap-2 mb-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600">
            <ShieldCheck className="h-4 w-4 text-white" aria-hidden="true" />
          </div>
          <span className="font-bold text-slate-900">Aurea</span>
        </div>
        <p className="text-sm text-slate-400">
          &copy; 2026 Aurea &mdash; AI-Powered Property Risk Intelligence
          <span className="mx-2 text-slate-300">|</span>
          Powered by AWS Bedrock &amp; MongoDB Atlas
        </p>
      </footer>
    </div>
  )
}
