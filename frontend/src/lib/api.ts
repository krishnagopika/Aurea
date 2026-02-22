const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ─── Error Type ───────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// ─── Response Types ───────────────────────────────────────────────────────────

export interface AuthResponse {
  access_token: string
  token_type: string
}

export interface RiskScores {
  flood_risk_score: number
  property_age_risk_score: number
  planning_development_risk_score: number
  locality_safety_score: number
  overall_risk_score: number
}

export interface RiskFactor {
  name: string
  score: number
  weight: number
  reasoning: string
}

export interface PropertyDetails {
  property_type: string        // House, Flat, Maisonette, Bungalow
  built_form: string           // Detached, Semi-Detached, Terraced, End-Terrace
  age_band: string             // e.g. "England and Wales: 1967-1975"
  epc_rating: string           // A–G
  floor_area_m2: number | null
  habitable_rooms: number | null
  wall_type: string            // e.g. "Cavity wall, as built, no insulation"
  roof_type: string
  floor_type: string
  glazing: string              // "double glazing", "single glazing"
  heating: string
  confirmed_address: string
}

export interface UnderwritingDecision {
  assessment_id?: string
  decision: 'ACCEPT' | 'REFER' | 'DECLINE'
  risk_scores: RiskScores
  premium_multiplier: number
  plain_english_narrative: string
  risk_factors?: RiskFactor[]
  policy_citations: string[]
  data_warnings: string[]
  property_details?: PropertyDetails | null
  created_at?: string
  address?: string
  postcode?: string
  id?: string
}

export interface HistoryItem {
  id: string
  address: string
  postcode: string
  decision: 'ACCEPT' | 'REFER' | 'DECLINE'
  risk_scores: RiskScores
  premium_multiplier: number
  plain_english_narrative: string
  policy_citations: string[]
  data_warnings: string[]
  created_at: string
}

// Raw shape the backend actually returns
interface RawAssessmentResponse {
  assessment_id: string
  decision: string
  overall_risk_score: number
  premium_multiplier: number
  flood_risk_score: number
  planning_risk_score: number
  property_age_risk_score: number
  locality_safety_score: number
  risk_factors?: RiskFactor[]
  plain_english_narrative: string
  data_warnings: string[]
  policy_citations?: string[]
  property_details?: PropertyDetails | null
  address?: string
  postcode?: string
}

function normaliseDecision(raw: string): 'ACCEPT' | 'REFER' | 'DECLINE' {
  const upper = raw.toUpperCase()
  if (upper === 'ACCEPT' || upper === 'REFER' || upper === 'DECLINE') {
    return upper as 'ACCEPT' | 'REFER' | 'DECLINE'
  }
  return 'REFER'
}

function transformAssessment(raw: RawAssessmentResponse): UnderwritingDecision {
  return {
    assessment_id: raw.assessment_id,
    decision: normaliseDecision(raw.decision),
    risk_scores: {
      overall_risk_score: raw.overall_risk_score,
      flood_risk_score: raw.flood_risk_score,
      property_age_risk_score: raw.property_age_risk_score,
      planning_development_risk_score: raw.planning_risk_score,
      locality_safety_score: raw.locality_safety_score ?? 25,
    },
    premium_multiplier: raw.premium_multiplier,
    plain_english_narrative: raw.plain_english_narrative ?? '',
    risk_factors: raw.risk_factors ?? [],
    policy_citations: raw.policy_citations ?? [],
    data_warnings: raw.data_warnings ?? [],
    property_details: raw.property_details ?? null,
    address: raw.address,
    postcode: raw.postcode,
  }
}

// ─── Core Request Helper ──────────────────────────────────────────────────────

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown
    try {
      body = await res.json()
    } catch {
      body = await res.text()
    }
    const message =
      typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : `HTTP ${res.status}`
    throw new ApiError(res.status, message, body)
  }
  return res.json() as Promise<T>
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  return handleResponse<T>(res)
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export async function register(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>('/api/v1/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
}

// ─── Underwriting ─────────────────────────────────────────────────────────────

export type PipelineEvent =
  | { type: 'agent_start'; agent: string }
  | { type: 'agent_end'; agent: string }
  | { type: 'result'; data: UnderwritingDecision }
  | { type: 'error'; message: string }

/**
 * Stream real-time agent events via SSE (POST with ReadableStream).
 * Calls onEvent for each parsed SSE event, resolves with the final result.
 */
export async function runAssessmentStream(
  address: string,
  postcode: string,
  token: string,
  onEvent: (event: PipelineEvent) => void,
): Promise<UnderwritingDecision> {
  const res = await fetch(`${BASE}/api/v1/underwriting/assess-stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ address, postcode }),
  })

  if (!res.ok) {
    let body: unknown
    try { body = await res.json() } catch { body = await res.text() }
    const message =
      typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : `HTTP ${res.status}`
    throw new ApiError(res.status, message, body)
  }

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult: UnderwritingDecision | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // Process complete lines
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? '' // keep incomplete last line

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6).trim()
      if (raw === '[DONE]') break

      try {
        const payload = JSON.parse(raw) as {
          type: string
          agent?: string
          data?: RawAssessmentResponse
          message?: string
        }

        if (payload.type === 'agent_start' || payload.type === 'agent_end') {
          onEvent({ type: payload.type, agent: payload.agent! })
        } else if (payload.type === 'result' && payload.data) {
          finalResult = transformAssessment(payload.data)
          onEvent({ type: 'result', data: finalResult })
        } else if (payload.type === 'error') {
          onEvent({ type: 'error', message: payload.message ?? 'Unknown error' })
        }
      } catch {
        // malformed JSON line — skip
      }
    }
  }

  if (!finalResult) throw new ApiError(500, 'Stream ended without a result')
  return finalResult
}

export async function runAssessment(
  address: string,
  postcode: string,
  token: string,
): Promise<UnderwritingDecision> {
  const raw = await request<RawAssessmentResponse>('/api/v1/underwriting/assess', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ address, postcode }),
  })
  return transformAssessment(raw)
}

export async function getHistory(token: string): Promise<HistoryItem[]> {
  const raws = await request<RawAssessmentResponse[]>('/api/v1/underwriting/history', {
    headers: { Authorization: `Bearer ${token}` },
  })
  return raws.map((raw) => {
    const d = transformAssessment(raw)
    return {
      id: raw.assessment_id,
      address: raw.address ?? '',
      postcode: raw.postcode ?? '',
      decision: d.decision,
      risk_scores: d.risk_scores,
      premium_multiplier: d.premium_multiplier,
      plain_english_narrative: d.plain_english_narrative,
      policy_citations: d.policy_citations,
      data_warnings: d.data_warnings,
      created_at: '',
    }
  })
}
