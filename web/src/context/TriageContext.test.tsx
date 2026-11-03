import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import React from 'react'
import { TriageProvider, useTriage } from './TriageContext'
import { api, type TriageApiRequest, type TriageResponse } from '@/lib/api'

// Mock the API layer
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  const mockRunTriage = vi.fn()
  const mockStreamTriage = vi.fn(
    async (
      payload: TriageApiRequest,
      onEvent?: (event: import('@/types/execution').TriageLifecycleEvent) => void
    ) => {
      if (typeof onEvent === 'function') {
        onEvent({
          request_id: 'mock-req',
          sequence: 1,
          timestamp: new Date().toISOString(),
          event_type: 'stage.started',
          stage: 'normalise',
          status: 'running',
          safe_summary: 'Mock normalise started',
        })
      }
      return mockRunTriage(payload)
    }
  )
  return {
    ...actual,
    api: {
      ...actual.api,
      runTriage: mockRunTriage,
      streamTriage: mockStreamTriage,
    },
  }
})

const makeRequest = (
  age: string,
  sex: 'male' | 'female' | 'other' | 'unknown',
  weight: string
): TriageApiRequest => ({
  patient: {
    assessed_at: '2026-01-01T12:00:00Z',
    age: { value: age, unit: 'years' },
    sex,
    pregnancy: 'not_applicable',
    weight_kg: { source: 'measured', value: weight },
    vitals: {
      heart_rate_bpm: { source: 'measured', value: 75 },
      systolic_bp_mmhg: { source: 'measured', value: 120 },
    },
    allergy_history_status: 'confirmed_nkda',
    medication_history_status: 'confirmed_none',
    allergies: [],
    medications: [],
  },
  include_complaint_in_llm: false,
  overrides: [],
})

const makeResponse = (
  age: string,
  sex: 'male' | 'female' | 'other' | 'unknown',
  weight: string,
  headline: string
): TriageResponse => ({
  engine: {
    verdict: 'CHECKED_CLEAR',
    checks_run: 10,
    checks_skipped: [],
    unresolved_entities: [],
    ruleset_coverage: [],
    coverage_gaps: [],
    baseline_alerts: [],
    plan_alerts: [],
    score: null,
  },
  verified_steps: [],
  retrieval: null,
  explanation: {
    headline,
    plain_language_summary: 'Summary',
    outcome_reasons: [],
    retrieval_explanation: '',
    evidence_summary: '',
    completed_checks: [],
    unresolved_checks: [],
    generation_disclosure: '',
    permitted_ui_actions: [],
  },
  patient: {
    assessed_at: '2026-01-01T12:00:00Z',
    age: { value: age, unit: 'years' },
    sex,
    pregnancy: 'not_applicable',
    weight_kg: { source: 'measured', value: weight },
    vitals: {},
    allergy_history_status: 'confirmed_nkda',
    medication_history_status: 'confirmed_none',
    allergies: [],
    medications: [],
  },
  input_patient: {
    assessed_at: '2026-01-01T12:00:00Z',
    age: { value: age, unit: 'years' },
    sex,
    pregnancy: 'not_applicable',
    weight_kg: { source: 'measured', value: weight },
    vitals: {},
    allergy_history_status: 'confirmed_nkda',
    medication_history_status: 'confirmed_none',
    allergies: [],
    medications: [],
  },
  llm_fallback_mode: false,
  audit_hash: 'hash-123',
  provider_info: {
    generation_mode: 'deterministic_mock',
    requested_profile: 'COMPLIANT',
    retrieval_backend: 'bm25',
  },
})

// Test harness component
const TestConsumer: React.FC<{
  onStateUpdate?: (state: ReturnType<typeof useTriage>) => void
}> = ({ onStateUpdate }) => {
  const triage = useTriage()
  React.useEffect(() => {
    onStateUpdate?.(triage)
  })

  return (
    <div>
      <div data-testid="req-age">{triage.patientRequest?.patient.age.value ?? 'none'}</div>
      <div data-testid="res-headline">{triage.triageResult?.explanation?.headline ?? 'none'}</div>
      <div data-testid="is-loading">{triage.isLoading ? 'loading' : 'idle'}</div>
      <button
        data-testid="eval-case-1"
        onClick={() => triage.evaluatePatient(makeRequest('30', 'male', '70'))}
      >
        Eval 1
      </button>
      <button
        data-testid="eval-case-2"
        onClick={() => triage.evaluatePatient(makeRequest('55', 'female', '85'))}
      >
        Eval 2
      </button>
      <button
        data-testid="set-req-case-2"
        onClick={() => triage.setPatientRequest(makeRequest('55', 'female', '85'))}
      >
        Set Req 2
      </button>
    </div>
  )
}

describe('TriageContext Stale Result Prevention', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.clearAllMocks()
  })

  it('submits case 1, updates patient details, and verifies the old result cannot appear for the new request', async () => {
    const mockRunTriage = vi.mocked(api.runTriage)
    mockRunTriage.mockResolvedValueOnce(makeResponse('30', 'male', '70', 'Case 1 Cleared'))

    render(
      <TriageProvider>
        <TestConsumer />
      </TriageProvider>
    )

    // Initially nothing loaded
    expect(screen.getByTestId('req-age').textContent).toBe('none')
    expect(screen.getByTestId('res-headline').textContent).toBe('none')

    // 1. Evaluate Case 1
    await act(async () => {
      screen.getByTestId('eval-case-1').click()
    })

    expect(screen.getByTestId('req-age').textContent).toBe('30')
    expect(screen.getByTestId('res-headline').textContent).toBe('Case 1 Cleared')

    // 2. Clinician modifies patient details (Case 2: 55yo female)
    act(() => {
      screen.getByTestId('set-req-case-2').click()
    })

    // Request is now Case 2 (age 55)
    expect(screen.getByTestId('req-age').textContent).toBe('55')
    // STALE RESULT PREVENTION: Result for Case 1 MUST be cleared and cannot leak to Case 2!
    expect(screen.getByTestId('res-headline').textContent).toBe('none')
    expect(sessionStorage.getItem('triagerag_triage_result')).toBeNull()
  })

  it('clears previous result immediately when a new evaluation starts, preventing in-flight stale display', async () => {
    const mockRunTriage = vi.mocked(api.runTriage)
    mockRunTriage.mockResolvedValueOnce(makeResponse('30', 'male', '70', 'Case 1 Cleared'))

    let resolveCase2: ((res: TriageResponse) => void) | null = null
    mockRunTriage.mockImplementationOnce(
      () =>
        new Promise<TriageResponse>((resolve) => {
          resolveCase2 = resolve
        })
    )

    render(
      <TriageProvider>
        <TestConsumer />
      </TriageProvider>
    )

    // Complete Case 1
    await act(async () => {
      screen.getByTestId('eval-case-1').click()
    })
    expect(screen.getByTestId('res-headline').textContent).toBe('Case 1 Cleared')

    // Start Case 2 evaluation (async in-flight)
    act(() => {
      screen.getByTestId('eval-case-2').click()
    })

    // While loading Case 2, Case 1 result MUST NOT be visible!
    expect(screen.getByTestId('is-loading').textContent).toBe('loading')
    expect(screen.getByTestId('res-headline').textContent).toBe('none')

    // Finish Case 2
    await act(async () => {
      resolveCase2!(makeResponse('55', 'female', '85', 'Case 2 Cleared'))
    })

    expect(screen.getByTestId('is-loading').textContent).toBe('idle')
    expect(screen.getByTestId('res-headline').textContent).toBe('Case 2 Cleared')
  })

  it('purges mismatched session storage result on initialization', () => {
    // Seed sessionStorage with mismatched request and result
    const req1 = makeRequest('30', 'male', '70')
    const res2 = makeResponse('55', 'female', '85', 'Mismatched Old Result')
    sessionStorage.setItem('triagerag_patient_request', JSON.stringify(req1))
    sessionStorage.setItem('triagerag_triage_result', JSON.stringify(res2))

    render(
      <TriageProvider>
        <TestConsumer />
      </TriageProvider>
    )

    // Request is restored (30yo)
    expect(screen.getByTestId('req-age').textContent).toBe('30')
    // Stale mismatched result MUST be purged, not restored!
    expect(screen.getByTestId('res-headline').textContent).toBe('none')
    expect(sessionStorage.getItem('triagerag_triage_result')).toBeNull()
  })
})
