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

export interface UnderwritingDecision {
  assessment_id?: string
  decision: 'ACCEPT' | 'REFER' | 'DECLINE'
  risk_scores: RiskScores
  premium_multiplier: number
  plain_english_narrative: string
  risk_factors?: RiskFactor[]
  policy_citations: string[]
  data_warnings: string[]
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
