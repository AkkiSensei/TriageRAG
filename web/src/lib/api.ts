import { QueryClient } from '@tanstack/react-query'
import type { components } from '@/types/api'
import type { TriageLifecycleEvent } from '@/types/execution'
export type {
  TriageLifecycleEvent,
  TriageLifecycleEventType,
  StageStatus,
  ProcessStageDefinition,
} from '@/types/execution'
export { PROCESS_STAGES } from '@/types/execution'

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
export type TriageExplanation = components['schemas']['TriageExplanation']
export type ActionPlan = components['schemas']['ActionPlan']
export type ActionStep = components['schemas']['ActionStep']
export type MedicationInstruction = components['schemas']['MedicationInstruction']
export type MonitoringStep = components['schemas']['MonitoringStep']
export type EscalationStep = components['schemas']['EscalationStep']
export type ConfidenceReport = components['schemas']['ConfidenceReport']
export type DataQualityReport = components['schemas']['DataQualityReport']
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

  streamTriage: async (
    payload: TriageApiRequest,
    onEvent: (event: TriageLifecycleEvent) => void,
    signal?: AbortSignal
  ): Promise<TriageResponse> => {
    const origin =
      typeof window !== 'undefined' && window.location?.origin
        ? window.location.origin
        : 'http://localhost:8000'
    const fullUrl = `${origin}${API_BASE}/triage/stream`

    const response = await fetch(fullUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal,
    })

    if (!response.ok) {
      let errorData: unknown
      try {
        errorData = await response.json()
      } catch {
        errorData = await response.text()
      }
      throw new ApiError(response.status, `Stream failed with status ${response.status}`, errorData)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new ApiError(500, 'ReadableStream not supported by response')
    }

    const decoder = new TextDecoder()
    let buffer = ''
    let finalResponse: TriageResponse | null = null

    let streamDone = false
    try {
      while (!streamDone) {
        const { done, value } = await reader.read()
        if (done) {
          streamDone = true
          break
        }
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')

        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          if (!part.trim()) continue
          const lines = part.split('\n')
          let dataStr = ''

          for (const line of lines) {
            if (line.startsWith('data:')) {
              dataStr = line.slice(5).trim()
            }
          }

          if (dataStr) {
            try {
              const eventObj: TriageLifecycleEvent = JSON.parse(dataStr)
              onEvent(eventObj)
              if (eventObj.event_type === 'run.completed' && eventObj.data) {
                finalResponse = eventObj.data as TriageResponse
              }
            } catch (err) {
              console.error('Failed to parse SSE event JSON:', err)
            }
          }
        }
      }
    } finally {
      reader.releaseLock()
    }

    if (!finalResponse) {
      throw new ApiError(500, 'Stream ended without terminal run.completed event')
    }

    return finalResponse
  },

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

  // Ask the Corpus (T7.4)
  askCorpus: (payload: { question: string; population?: string; syndrome?: string; top_k?: number }) =>
    request<{
      question: string
      answer: string
      abstained: boolean
      abstain_reason?: string
      citations: Array<{ chunk_id: string; doc_id: string; section: string; license: string; exact_quote: string }>
      generator_badge: string
    }>('/corpus/ask', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Alert Why (T7.4)
  explainAlert: (payload: { alert: Alert; patient: unknown }) =>
    request<{
      rule_id: string
      rule_type: string
      severity: string
      consequence: string
      action: string
      matched_facts: string[]
      unknown_facts: string[]
      severity_rationale: string
      unestablished_scope: string[]
      provenance: Record<string, unknown>
    }>('/triage/alert-why', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
