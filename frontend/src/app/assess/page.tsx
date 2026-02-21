'use client'

import { useState, useEffect, useRef, useCallback, type FormEvent, lazy, Suspense } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  MapPin,
  Hash,
  Play,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  AlertTriangle,
  ShieldCheck,
  BookOpen,
  ExternalLink,
  CheckCircle,
  XCircle,
  Search,
  Map,
} from 'lucide-react'
import Navbar from '@/components/Navbar'
import DecisionBadge from '@/components/DecisionBadge'
import RiskScoreRing from '@/components/RiskScoreRing'
import RiskScoreBar from '@/components/RiskScoreBar'
import AgentPipelineStatus, { type Agent, type AgentStatus } from '@/components/AgentPipelineStatus'
import TypingNarrative from '@/components/TypingNarrative'
import { Button } from '@/components/ui/button'
import { runAssessment, type UnderwritingDecision, ApiError } from '@/lib/api'
import type { PickedLocation } from '@/components/LocationMapPicker'

// Dynamic import — Leaflet reads `window` on load, breaks SSR
const LocationMapPicker = lazy(() => import('@/components/LocationMapPicker'))

// ─── Initial agent definitions ────────────────────────────────────────────────

const INITIAL_AGENTS: Agent[] = [
  {
    id: 'PropertyValuationAgent',
    name: 'PropertyValuationAgent',
    description: 'IBEX Planning Data — property valuation & development history',
    status: 'pending',
  },
  {
    id: 'FloodRiskAgent',
    name: 'FloodRiskAgent',
    description: 'Flood Zone Classification — Environment Agency data',
    status: 'pending',
  },
  {
    id: 'EnvironmentalDataAgent',
    name: 'EnvironmentalDataAgent',
    description: 'EPC Property Data — energy & environmental performance',
    status: 'pending',
  },
  {
    id: 'LocalitySafetyAgent',
    name: 'LocalitySafetyAgent',
    description: 'Crime & Safety Data — Police UK street-level crime analysis',
    status: 'pending',
  },
  {
    id: 'PolicyAgent',
    name: 'PolicyAgent',
    description: 'Policy Retrieval — applicable underwriting policies',
    status: 'pending',
  },
  {
    id: 'CoordinatorAgent',
    name: 'CoordinatorAgent',
    description: 'Underwriting Decision — coordinating final risk assessment',
    status: 'pending',
  },
  {
    id: 'ExplainabilityAgent',
    name: 'ExplainabilityAgent',
    description: 'Risk Narrative — plain-English decision explanation',
    status: 'pending',
  },
]

// ─── Data sources info box ────────────────────────────────────────────────────

const DATA_SOURCES = [
  { label: 'Flood Zone Classification', source: 'Environment Agency' },
  { label: 'Planning Applications & History', source: 'IBEX Planning Data' },
  { label: 'Energy Performance Certificate', source: 'EPC Register' },
  { label: 'Street-Level Crime Data', source: 'Police UK API' },
  { label: 'Applicable Policy Rules', source: 'Underwriting Policy DB' },
]

// ─── Page Component ───────────────────────────────────────────────────────────

export default function AssessPage() {
  const router = useRouter()
  const [token, setToken] = useState<string | null>(null)
  const [address, setAddress] = useState('')
  const [postcode, setPostcode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<UnderwritingDecision | null>(null)
  const [agents, setAgents] = useState<Agent[]>(INITIAL_AGENTS)
  const [pipelineVisible, setPipelineVisible] = useState(false)
  const [warningsOpen, setWarningsOpen] = useState(false)

  // ── Address autocomplete state ────────────────────────────────────────────
  interface NominatimResult {
    place_id: number
    display_name: string
    address: {
      house_number?: string
      road?: string
      city?: string
      town?: string
      village?: string
      postcode?: string
    }
  }

  const [suggestions, setSuggestions] = useState<NominatimResult[]>([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [fetchingSuggestions, setFetchingSuggestions] = useState(false)
  const addressWrapperRef = useRef<HTMLDivElement>(null)
  const addressDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Map picker state ──────────────────────────────────────────────────────
  const [showMap, setShowMap] = useState(false)

  // ── Postcode validation state ─────────────────────────────────────────────
  type PostcodeValidity = 'valid' | 'invalid' | 'checking' | null
  const [postcodeValid, setPostcodeValid] = useState<PostcodeValidity>(null)
  const postcodeDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auth guard
  useEffect(() => {
    const t = localStorage.getItem('aurea_token')
    if (!t) {
      router.replace('/login')
    } else {
      setToken(t)
    }
  }, [router])

  // ── Close dropdown on outside click ──────────────────────────────────────
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        addressWrapperRef.current &&
        !addressWrapperRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // ── Address autocomplete fetch ────────────────────────────────────────────
  const fetchSuggestions = useCallback(async (query: string) => {
    setFetchingSuggestions(true)
    try {
      const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query + ', UK')}&countrycodes=gb&format=json&limit=5&addressdetails=1`
      const res = await fetch(url, {
        headers: { 'Accept-Language': 'en' },
      })
      if (!res.ok) return
      const data: NominatimResult[] = await res.json()
      setSuggestions(data)
      setShowDropdown(data.length > 0)
    } catch {
      // silently ignore network errors in autocomplete
    } finally {
      setFetchingSuggestions(false)
    }
  }, [])

  // ── Postcode validation ───────────────────────────────────────────────────
  const UK_POSTCODE_REGEX = /^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}$/i

  const validatePostcode = useCallback(async (value: string) => {
    if (!value.trim()) {
      setPostcodeValid(null)
      return
    }
    if (!UK_POSTCODE_REGEX.test(value.trim())) {
      setPostcodeValid('invalid')
      return
    }
    setPostcodeValid('checking')
    try {
      const normalised = value.trim().replace(/\s+/g, '')
      const res = await fetch(`https://api.postcodes.io/postcodes/${encodeURIComponent(normalised)}`)
      setPostcodeValid(res.status === 200 ? 'valid' : 'invalid')
    } catch {
      // If the network request fails, fall back to regex result (passed above)
      setPostcodeValid('valid')
    }
  }, [])

  const handleAddressChange = (value: string) => {
    setAddress(value)
    if (addressDebounceRef.current) clearTimeout(addressDebounceRef.current)
    if (value.length < 4) {
      setSuggestions([])
      setShowDropdown(false)
      return
    }
    addressDebounceRef.current = setTimeout(() => {
      fetchSuggestions(value)
    }, 500)
  }

  const formatSuggestionAddress = (result: NominatimResult): string => {
    const { house_number, road, city, town, village } = result.address
    const locality = city ?? town ?? village ?? ''
    const parts = [house_number, road, locality].filter(Boolean)
    return parts.length > 0 ? parts.join(', ') : result.display_name
  }

  const handleSuggestionClick = (result: NominatimResult) => {
    const formatted = formatSuggestionAddress(result)
    setAddress(formatted)
    if (result.address.postcode) {
      const pc = result.address.postcode.toUpperCase()
      setPostcode(pc)
      validatePostcode(pc)
    }
    setShowDropdown(false)
    setSuggestions([])
  }

  const handleMapLocationSelect = (loc: PickedLocation) => {
    if (loc.address) setAddress(loc.address)
    if (loc.postcode) {
      const pc = loc.postcode.toUpperCase()
      setPostcode(pc)
      validatePostcode(pc)
    }
  }

  const handlePostcodeChange = (value: string) => {
    const upper = value.toUpperCase()
    setPostcode(upper)
    if (!upper.trim()) {
      setPostcodeValid(null)
      if (postcodeDebounceRef.current) clearTimeout(postcodeDebounceRef.current)
      return
    }
    if (postcodeDebounceRef.current) clearTimeout(postcodeDebounceRef.current)
    postcodeDebounceRef.current = setTimeout(() => {
      validatePostcode(upper)
    }, 500)
  }

  const handlePostcodeBlur = () => {
    if (postcodeDebounceRef.current) clearTimeout(postcodeDebounceRef.current)
    validatePostcode(postcode)
  }

  // ── Simulate agent progress in parallel with real API call ────────────────
  const simulateAgentProgress = async () => {
    setAgents(INITIAL_AGENTS.map((a) => ({ ...a, status: 'pending' as AgentStatus })))
    setPipelineVisible(true)

    for (let i = 0; i < INITIAL_AGENTS.length; i++) {
      setAgents((prev) =>
        prev.map((a, idx) => (idx === i ? { ...a, status: 'running' as AgentStatus } : a)),
      )
      await new Promise<void>((resolve) => setTimeout(resolve, 900 + Math.random() * 400))
      setAgents((prev) =>
        prev.map((a, idx) => (idx === i ? { ...a, status: 'complete' as AgentStatus } : a)),
      )
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!token) return

    setError(null)
    setResult(null)
    setWarningsOpen(false)

    if (!address.trim() || !postcode.trim()) {
      setError('Please enter both address and postcode.')
      return
    }

    if (postcodeValid === 'invalid' || postcodeValid === 'checking') {
      setError('Please enter a valid UK postcode before submitting.')
      return
    }

    if (postcodeValid === null) {
      // Hasn't been validated yet — run sync regex check before blocking
      if (!UK_POSTCODE_REGEX.test(postcode.trim())) {
        setError('Please enter a valid UK postcode before submitting.')
        return
      }
    }

    setLoading(true)

    // Fire agent simulation (non-blocking)
    simulateAgentProgress()

    try {
      const assessment = await runAssessment(
        address.trim(),
        postcode.trim().toUpperCase(),
        token,
      )
      setResult(assessment)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          localStorage.removeItem('aurea_token')
          router.replace('/login')
          return
        }
        setError(err.message)
      } else {
        setError('Assessment failed. Please check your connection and try again.')
      }
      setAgents(INITIAL_AGENTS.map((a) => ({ ...a, status: 'pending' as AgentStatus })))
    } finally {
      setLoading(false)
    }
  }

  // Loading screen while auth resolves
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
        {/* Page header */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="mb-8"
        >
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Property Assessment</h1>
          <p className="mt-1.5 text-sm text-slate-500">
            Enter a UK property address to receive an instant AI-powered underwriting decision.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-8 items-start">
          {/* ═══════════════════════════════════════════════════════════════
              LEFT COLUMN — Input form + Agent pipeline
          ═══════════════════════════════════════════════════════════════ */}
          <div className="space-y-5">
            {/* Input card */}
            <motion.div
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1, duration: 0.45 }}
              className="rounded-2xl bg-white border border-slate-200 shadow-sm p-6"
            >
              <form onSubmit={handleSubmit} className="space-y-5" noValidate>
                {/* Address input with autocomplete */}
                <div className="space-y-1.5" ref={addressWrapperRef}>
                  <label
                    htmlFor="address"
                    className="flex items-center gap-2 text-sm font-medium text-slate-700"
                  >
                    <MapPin className="h-4 w-4 text-blue-600" aria-hidden="true" />
                    Full Address
                  </label>
                  <div className="relative">
                    <input
                      id="address"
                      type="text"
                      value={address}
                      onChange={(e) => handleAddressChange(e.target.value)}
                      onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
                      onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
                      placeholder="e.g. 10 Downing Street, Westminster, London"
                      required
                      disabled={loading}
                      autoComplete="off"
                      className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 pr-10 text-sm text-slate-900 placeholder-slate-400 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all duration-200 disabled:opacity-50 disabled:bg-slate-50"
                    />
                    {fetchingSuggestions && (
                      <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5 text-slate-400">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                        <span className="text-[11px]">Searching...</span>
                      </div>
                    )}
                    {showDropdown && suggestions.length > 0 && (
                      <ul
                        role="listbox"
                        aria-label="Address suggestions"
                        className="absolute left-0 right-0 top-full mt-1 z-50 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-y-auto"
                      >
                        {suggestions.map((result) => (
                          <li
                            key={result.place_id}
                            role="option"
                            aria-selected={false}
                            onMouseDown={(e) => {
                              // Use mousedown so it fires before the input's onBlur
                              e.preventDefault()
                              handleSuggestionClick(result)
                            }}
                            className="px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-b-0"
                          >
                            <p className="text-sm font-medium text-slate-800 truncate">
                              {formatSuggestionAddress(result)}
                            </p>
                            <p className="text-[11px] text-slate-400 truncate mt-0.5">
                              {result.display_name}
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>

                {/* Postcode input with validation */}
                <div className="space-y-1.5">
                  <label
                    htmlFor="postcode"
                    className="flex items-center gap-2 text-sm font-medium text-slate-700"
                  >
                    <Hash className="h-4 w-4 text-blue-600" aria-hidden="true" />
                    Postcode
                  </label>
                  <div className="relative">
                    <input
                      id="postcode"
                      type="text"
                      value={postcode}
                      onChange={(e) => handlePostcodeChange(e.target.value)}
                      onBlur={handlePostcodeBlur}
                      placeholder="e.g. SW1A 2AA"
                      required
                      disabled={loading}
                      aria-invalid={postcodeValid === 'invalid'}
                      aria-describedby={postcodeValid === 'invalid' ? 'postcode-error' : undefined}
                      className={[
                        'w-full rounded-lg border bg-white px-4 py-3 pr-10 text-sm font-mono text-slate-900 placeholder-slate-400 outline-none transition-all duration-200 disabled:opacity-50 disabled:bg-slate-50',
                        postcodeValid === 'valid'
                          ? 'border-green-400 focus:border-green-500 focus:ring-2 focus:ring-green-500/20'
                          : postcodeValid === 'invalid'
                          ? 'border-red-400 focus:border-red-500 focus:ring-2 focus:ring-red-500/20'
                          : 'border-slate-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20',
                      ].join(' ')}
                    />
                    {/* Validation status icon */}
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
                      {postcodeValid === 'checking' && (
                        <Loader2 className="h-4 w-4 animate-spin text-slate-400" aria-label="Validating postcode" />
                      )}
                      {postcodeValid === 'valid' && (
                        <CheckCircle className="h-4 w-4 text-green-500" aria-label="Valid postcode" />
                      )}
                      {postcodeValid === 'invalid' && (
                        <XCircle className="h-4 w-4 text-red-500" aria-label="Invalid postcode" />
                      )}
                    </div>
                  </div>
                  {/* Inline error message */}
                  <AnimatePresence>
                    {postcodeValid === 'invalid' && (
                      <motion.p
                        id="postcode-error"
                        key="postcode-error"
                        role="alert"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden text-xs text-red-600 flex items-center gap-1.5"
                      >
                        <Search className="h-3 w-3 shrink-0" aria-hidden="true" />
                        Enter a valid UK postcode (e.g. SW1A 2AA)
                      </motion.p>
                    )}
                  </AnimatePresence>
                </div>

                {/* Map picker toggle */}
                <div>
                  <button
                    type="button"
                    onClick={() => setShowMap((v) => !v)}
                    disabled={loading}
                    className="flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors disabled:opacity-40"
                  >
                    <Map className="h-4 w-4" aria-hidden="true" />
                    {showMap ? 'Hide map' : 'Pick location on map'}
                    {showMap ? (
                      <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                  </button>

                  <AnimatePresence>
                    {showMap && (
                      <motion.div
                        key="map-panel"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.3 }}
                        className="overflow-hidden mt-3"
                      >
                        <Suspense
                          fallback={
                            <div className="flex items-center justify-center h-[340px] rounded-xl bg-slate-50 border border-slate-200">
                              <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
                            </div>
                          }
                        >
                          <LocationMapPicker onLocationSelect={handleMapLocationSelect} />
                        </Suspense>
                        <p className="mt-2 text-xs text-slate-500">
                          Selecting on the map auto-fills the address and postcode above.
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Error */}
                <AnimatePresence>
                  {error && (
                    <motion.div
                      key="form-error"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.22 }}
                      className="overflow-hidden"
                    >
                      <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3.5">
                        <AlertCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" aria-hidden="true" />
                        <p className="text-sm text-red-700">{error}</p>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Submit button */}
                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  isLoading={loading}
                  className="w-full"
                >
                  {loading ? (
                    'Running Assessment...'
                  ) : (
                    <>
                      <Play className="h-4 w-4" aria-hidden="true" />
                      Run Assessment
                    </>
                  )}
                </Button>
              </form>
            </motion.div>

            {/* Agent pipeline */}
            <AnimatePresence>
              {pipelineVisible && (
                <motion.div
                  key="pipeline"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.35 }}
                >
                  <AgentPipelineStatus agents={agents} />
                </motion.div>
              )}
            </AnimatePresence>

            {/* Data sources info card (shown when idle) */}
            <AnimatePresence>
              {!pipelineVisible && !result && (
                <motion.div
                  key="info-card"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ delay: 0.25, duration: 0.4 }}
                  className="rounded-xl bg-white border border-slate-200 shadow-sm p-5"
                >
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-4">
                    What gets analysed
                  </h3>
                  <div className="space-y-3">
                    {DATA_SOURCES.map(({ label, source }) => (
                      <div key={label} className="flex items-center justify-between">
                        <span className="text-sm text-slate-700">{label}</span>
                        <span className="text-[11px] text-slate-500 font-mono bg-slate-100 px-2 py-0.5 rounded">
                          {source}
                        </span>
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* ═══════════════════════════════════════════════════════════════
              RIGHT COLUMN — Results panel
          ═══════════════════════════════════════════════════════════════ */}
          <div className="space-y-5">
            <AnimatePresence mode="wait">
              {result ? (
                <motion.div
                  key="results"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ duration: 0.45, ease: 'easeOut' }}
                  className="space-y-5"
                >
                  {/* ── Decision + Ring card ── */}
                  <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-6">
                    {/* Decision label + badge */}
                    <div className="mb-5">
                      <p className="text-[10px] text-slate-400 uppercase tracking-widest mb-2 font-medium">
                        Underwriting Decision
                      </p>
                      <DecisionBadge decision={result.decision} size="lg" />
                    </div>

                    {/* Ring + multiplier row */}
                    <div className="flex items-center justify-around gap-4 mb-5">
                      <RiskScoreRing
                        score={result.risk_scores.overall_risk_score}
                        size={130}
                        strokeWidth={10}
                      />
                      <div className="text-center">
                        <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">
                          Premium Multiplier
                        </p>
                        <p className="text-4xl font-black text-slate-900 tabular-nums">
                          {result.premium_multiplier.toFixed(2)}
                          <span className="text-blue-600 text-2xl ml-0.5">&times;</span>
                        </p>
                        <p className="text-xs text-slate-400 mt-0.5">base rate</p>
                      </div>
                    </div>

                    {/* Address chip */}
                    <div className="flex items-center gap-2 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-sm">
                      <MapPin className="h-3.5 w-3.5 text-blue-600 shrink-0" aria-hidden="true" />
                      <span className="text-slate-600 truncate">
                        {result.address || address}, {result.postcode || postcode}
                      </span>
                    </div>
                  </div>

                  {/* ── Risk Breakdown ── */}
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15, duration: 0.4 }}
                    className="rounded-2xl bg-white border border-slate-200 shadow-sm p-6"
                  >
                    <div className="flex items-center gap-2 mb-5">
                      <TrendingUp className="h-4 w-4 text-blue-600" aria-hidden="true" />
                      <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                        Risk Factor Breakdown
                      </h2>
                    </div>
                    <div className="space-y-5">
                      <RiskScoreBar
                        label="Flood Risk"
                        score={result.risk_scores.flood_risk_score}
                        weight={40}
                        delay={0}
                      />
                      <RiskScoreBar
                        label="Property Age Risk"
                        score={result.risk_scores.property_age_risk_score}
                        weight={25}
                        delay={200}
                      />
                      <RiskScoreBar
                        label="Planning & Development Risk"
                        score={result.risk_scores.planning_development_risk_score}
                        weight={20}
                        delay={400}
                      />
                      <RiskScoreBar
                        label="Locality & Crime Risk"
                        score={result.risk_scores.locality_safety_score}
                        weight={15}
                        delay={600}
                      />
                    </div>
                  </motion.div>

                  {/* ── AI Narrative ── */}
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.25, duration: 0.4 }}
                    className="rounded-2xl overflow-hidden border border-blue-100 bg-blue-50"
                  >
                    {/* Header bar */}
                    <div className="flex items-center gap-3 px-5 py-3 border-b border-blue-100 bg-white">
                      <div className="flex items-center gap-2">
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-600 opacity-60" />
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-600" />
                        </span>
                        <ShieldCheck className="h-4 w-4 text-blue-600" aria-hidden="true" />
                        <span className="text-xs font-semibold text-blue-700 uppercase tracking-widest">
                          AI Risk Assessment
                        </span>
                      </div>
                      <span className="ml-auto text-[10px] text-slate-400">ExplainabilityAgent</span>
                    </div>

                    {/* Narrative */}
                    <div className="px-5 py-5">
                      <TypingNarrative
                        text={result.plain_english_narrative}
                        wordsPerSecond={10}
                      />
                    </div>
                  </motion.div>

                  {/* ── Policy Citations ── */}
                  {result.policy_citations && result.policy_citations.length > 0 && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.35, duration: 0.4 }}
                      className="rounded-2xl bg-white border border-slate-200 shadow-sm p-5"
                    >
                      <div className="flex items-center gap-2 mb-4">
                        <BookOpen className="h-4 w-4 text-violet-600" aria-hidden="true" />
                        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                          Policy Citations
                        </h3>
                      </div>
                      <ul className="space-y-2.5">
                        {result.policy_citations.map((citation, i) => (
                          <li key={i} className="flex items-start gap-3 text-sm">
                            <span className="shrink-0 flex h-5 w-5 items-center justify-center rounded-full bg-blue-50 text-[10px] text-blue-600 font-mono mt-0.5">
                              {i + 1}
                            </span>
                            <span className="text-slate-600 leading-relaxed">{citation}</span>
                          </li>
                        ))}
                      </ul>
                    </motion.div>
                  )}

                  {/* ── Data Warnings (collapsible) ── */}
                  {result.data_warnings && result.data_warnings.length > 0 && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.4, duration: 0.4 }}
                      className="rounded-2xl border border-amber-200 bg-amber-50 overflow-hidden"
                    >
                      <button
                        type="button"
                        onClick={() => setWarningsOpen((o) => !o)}
                        className="flex w-full items-center justify-between px-5 py-3.5 text-sm font-medium text-amber-700 hover:bg-amber-100 transition-colors"
                        aria-expanded={warningsOpen}
                      >
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                          Data Warnings ({result.data_warnings.length})
                        </div>
                        {warningsOpen ? (
                          <ChevronUp className="h-4 w-4" aria-hidden="true" />
                        ) : (
                          <ChevronDown className="h-4 w-4" aria-hidden="true" />
                        )}
                      </button>
                      <AnimatePresence>
                        {warningsOpen && (
                          <motion.div
                            key="warnings"
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.25 }}
                            className="overflow-hidden"
                          >
                            <ul className="px-5 pb-4 space-y-1.5">
                              {result.data_warnings.map((warning, i) => (
                                <li
                                  key={i}
                                  className="flex items-start gap-2 text-sm text-amber-700"
                                >
                                  <span className="text-amber-400 mt-0.5 shrink-0">•</span>
                                  {warning}
                                </li>
                              ))}
                            </ul>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  )}

                  {/* New assessment CTA */}
                  <Button
                    variant="secondary"
                    size="md"
                    className="w-full"
                    onClick={() => {
                      setResult(null)
                      setPipelineVisible(false)
                      setAgents(INITIAL_AGENTS.map((a) => ({ ...a, status: 'pending' as AgentStatus })))
                      setAddress('')
                      setPostcode('')
                      setPostcodeValid(null)
                      setSuggestions([])
                      setShowDropdown(false)
                      setShowMap(false)
                    }}
                  >
                    <ExternalLink className="h-4 w-4" aria-hidden="true" />
                    New Assessment
                  </Button>
                </motion.div>
              ) : (
                /* Empty / loading state */
                <motion.div
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0, scale: 0.97 }}
                  transition={{ duration: 0.3 }}
                  className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-20 text-center min-h-[400px]"
                >
                  {loading ? (
                    <>
                      <div className="relative mb-6">
                        <div className="h-16 w-16 rounded-full border-2 border-slate-200" />
                        <div className="absolute inset-0 h-16 w-16 rounded-full border-t-2 border-blue-600 animate-spin" />
                        <div className="absolute inset-2 h-12 w-12 rounded-full border-t border-blue-300 animate-spin" style={{ animationDuration: '1.5s', animationDirection: 'reverse' }} />
                      </div>
                      <p className="text-slate-900 font-semibold mb-1.5">Analysing Property Risk</p>
                      <p className="text-sm text-slate-500">AI agents are working in parallel...</p>
                    </>
                  ) : (
                    <>
                      <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-400">
                        <MapPin className="h-7 w-7" aria-hidden="true" />
                      </div>
                      <p className="text-slate-700 font-semibold mb-2">No assessment yet</p>
                      <p className="text-sm text-slate-400 max-w-xs leading-relaxed">
                        Enter a UK property address and postcode to receive an instant AI underwriting decision.
                      </p>
                    </>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  )
}
