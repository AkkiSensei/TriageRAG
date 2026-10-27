import { QueryClient } from '@tanstack/react-query'
import type { components } from '@/types/api'

export type TriageResponse = components['schemas']['TriageResponse']
export type TriageApiRequest = components['schemas']['TriageApiRequest']
export type ScenarioSummary = components['schemas']['ScenarioSummary']
export type ScenarioDetail = components['schemas']['ScenarioDetail']
export type HealthResponse = components['schemas']['HealthResponse']
export type RegistrySummaryResponse = components['schemas']['RegistrySummaryResponse']
export type RuleSummaryDto = components['schemas']['RuleSummaryDto']
export type ProtocolChunkDto = components['schemas']['ProtocolChunkDto']
export type AuditEntryDto = components['schemas']['AuditEntryDto']
export type AuditVerifyResponse = components['schemas']['AuditVerifyResponse']
export type EvalSummaryResponse = components['schemas']['EvalSummaryResponse']
export type Alert = components['schemas']['Alert']
export type EngineReport = components['schemas']['EngineReport']
export type PlanStepDraft = components['schemas']['PlanStepDraft']
export type VerifiedStep = components['schemas']['VerifiedStep']
export type OverrideRecord = components['schemas']['OverrideRecord']
export type { components }

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const API_BASE = '/api'

export class ApiError extends Error {
  constructor(public status: number, message: string, public data?: unknown) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    let errorData: unknown
    try {
      errorData = await response.json()
    } catch {
      errorData = await response.text()
    }
    let message = `API request failed with status ${response.status}`
    if (typeof errorData === 'object' && errorData !== null) {
      const errObj = errorData as Record<string, unknown>
      if (Array.isArray(errObj.errors) && errObj.errors.length > 0) {
        message = errObj.errors
          .map((e: { field?: string; message?: string }) => e.message || 'Invalid value')
          .join(', ')
      } else if (typeof errObj.detail === 'string') {
        message = errObj.detail
      }
    }
    throw new ApiError(response.status, message, errorData)
  }

  return response.json() as Promise<T>
}

export const api = {
  // Health
  getHealth: () => request<HealthResponse>('/health'),

  // Scenarios
  getScenarios: () => request<ScenarioSummary[]>('/scenarios'),
  getScenario: (id: string) => request<ScenarioDetail>(`/scenarios/${id}`),

  // Triage
  runTriage: (payload: TriageApiRequest) =>
    request<TriageResponse>('/triage', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Registry
  getRegistrySummary: () => request<RegistrySummaryResponse>('/registry/summary'),
  getRules: () => request<RuleSummaryDto[]>('/registry/rules'),

  // Protocols
  getProtocols: () => request<ProtocolChunkDto[]>('/protocols'),

  // Audit
  getAuditEntries: (limit = 100) => request<AuditEntryDto[]>(`/audit/entries?limit=${limit}`),
  verifyAuditChain: () => request<AuditVerifyResponse>('/audit/verify', { method: 'POST' }),

  // Eval
  getEvalSummary: () => request<EvalSummaryResponse>('/eval/summary'),
}
