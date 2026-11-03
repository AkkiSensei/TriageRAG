import React, { createContext, useContext, useState } from 'react'
import {
  api,
  type TriageApiRequest,
  type TriageResponse,
  type OverrideRecord,
  type ScenarioDetail,
  type TriageLifecycleEvent,
} from '@/lib/api'
import { createSyntheticDemoRequest, DEMO_SCENARIO_METADATA } from '@/lib/demoPatient'

interface TriageContextType {
  patientRequest: TriageApiRequest | null
  triageResult: TriageResponse | null
  liveEvents: TriageLifecycleEvent[]
  activeOverrides: OverrideRecord[]
  selectedScenario: ScenarioDetail | null
  isDemoActive: boolean
  isLoading: boolean
  error: string | null
  setPatientRequest: (req: TriageApiRequest | null) => void
  setSelectedScenario: (scenario: ScenarioDetail | null) => void
  loadDemoPatient: () => void
  clearDemo: () => void
  evaluatePatient: (req: TriageApiRequest) => Promise<TriageResponse>
  applyOverride: (override: OverrideRecord) => Promise<void>
  clearPatient: () => void
  clearLiveEvents: () => void
}

const TriageContext = createContext<TriageContextType | undefined>(undefined)

const STORAGE_KEY_REQ = 'triagerag_patient_request'
const STORAGE_KEY_RES = 'triagerag_triage_result'
const STORAGE_KEY_DEMO = 'triagerag_demo_active'
const STORAGE_KEY_EVENTS = 'triagerag_live_events'

export function computePatientFingerprint(patient: unknown): string {
  if (!patient || typeof patient !== 'object') return ''
  const p = patient as Record<string, unknown>
  const age = p.age as Record<string, unknown> | undefined
  const vitals = p.vitals as Record<string, unknown> | undefined
  const weight = p.weight_kg as Record<string, unknown> | undefined

  return JSON.stringify({
    age: age ? { val: String(age.value ?? ''), unit: String(age.unit ?? '') } : null,
    sex: String(p.sex ?? ''),
    pregnancy: String(p.pregnancy ?? ''),
    weight: weight ? { val: String(weight.value ?? ''), src: String(weight.source ?? '') } : null,
    vitals: vitals
      ? {
          hr: (vitals.heart_rate_bpm as Record<string, unknown>)?.value ?? null,
          sbp: (vitals.systolic_bp_mmhg as Record<string, unknown>)?.value ?? null,
          dbp: (vitals.diastolic_bp_mmhg as Record<string, unknown>)?.value ?? null,
          rr: (vitals.respiratory_rate_bpm as Record<string, unknown>)?.value ?? null,
          spo2: (vitals.spo2_percent as Record<string, unknown>)?.value ?? null,
          temp: (vitals.temperature_c as Record<string, unknown>)?.value ?? null,
          conf: (vitals.consciousness as Record<string, unknown>)?.value ?? null,
          o2: (vitals.supplemental_o2 as Record<string, unknown>)?.value ?? null,
        }
      : null,
    allergies: Array.isArray(p.allergies)
      ? p.allergies.map((a) => (a as Record<string, unknown>)?.raw_substance ?? '')
      : [],
    medications: Array.isArray(p.medications)
      ? p.medications.map((m) => (m as Record<string, unknown>)?.raw_text ?? '')
      : [],
    allergy_status: String(p.allergy_history_status ?? ''),
    med_status: String(p.medication_history_status ?? ''),
    syndrome: String(p.suspected_syndrome ?? ''),
  })
}

export const TriageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [patientRequest, _setPatientRequest] = useState<TriageApiRequest | null>(() => {
    if (typeof window === 'undefined') return null
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY_REQ)
      return saved ? JSON.parse(saved) : null
    } catch {
      return null
    }
  })

  const [triageResult, setTriageResult] = useState<TriageResponse | null>(() => {
    if (typeof window === 'undefined') return null
    try {
      const savedReq = sessionStorage.getItem(STORAGE_KEY_REQ)
      const savedRes = sessionStorage.getItem(STORAGE_KEY_RES)
      if (!savedRes) return null
      const res: TriageResponse = JSON.parse(savedRes)
      if (savedReq) {
        const req: TriageApiRequest = JSON.parse(savedReq)
        const reqFp = computePatientFingerprint(req.patient)
        const resFp = computePatientFingerprint(res.input_patient || res.patient)
        if (reqFp !== resFp) {
          // Stale mismatched result! Purge it.
          sessionStorage.removeItem(STORAGE_KEY_RES)
          return null
        }
      }
      return res
    } catch {
      return null
    }
  })

  const [isDemoActive, setIsDemoActive] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    try {
      return sessionStorage.getItem(STORAGE_KEY_DEMO) === 'true'
    } catch {
      return false
    }
  })

  const [liveEvents, setLiveEvents] = useState<TriageLifecycleEvent[]>(() => {
    if (typeof window === 'undefined') return []
    try {
      const savedEvents = sessionStorage.getItem(STORAGE_KEY_EVENTS)
      return savedEvents ? JSON.parse(savedEvents) : []
    } catch {
      return []
    }
  })

  const [activeOverrides, setActiveOverrides] = useState<OverrideRecord[]>([])
  const [selectedScenario, setSelectedScenario] = useState<ScenarioDetail | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const loadDemoPatient = () => {
    const demoReq = createSyntheticDemoRequest()
    setPatientRequest(demoReq)
    setTriageResult(null)
    clearLiveEvents()
    setActiveOverrides([])
    setSelectedScenario(DEMO_SCENARIO_METADATA)
    setIsDemoActive(true)
    setError(null)
    try {
      sessionStorage.setItem(STORAGE_KEY_REQ, JSON.stringify(demoReq))
      sessionStorage.removeItem(STORAGE_KEY_RES)
      sessionStorage.removeItem(STORAGE_KEY_EVENTS)
      sessionStorage.setItem(STORAGE_KEY_DEMO, 'true')
    } catch {
      // ignore storage errors
    }
  }

  const clearLiveEvents = () => {
    setLiveEvents([])
    try {
      sessionStorage.removeItem(STORAGE_KEY_EVENTS)
    } catch {
      // ignore storage errors
    }
  }

  const clearDemo = () => {
    setIsDemoActive(false)
    try {
      sessionStorage.removeItem(STORAGE_KEY_DEMO)
    } catch {
      // ignore storage errors
    }
    clearPatient()
  }

  const setPatientRequest = (req: TriageApiRequest | null) => {
    _setPatientRequest(req)
    if (!req) {
      setTriageResult(null)
      clearLiveEvents()
      try {
        sessionStorage.removeItem(STORAGE_KEY_REQ)
        sessionStorage.removeItem(STORAGE_KEY_RES)
      } catch {
        // ignore storage errors
      }
      return
    }
    try {
      sessionStorage.setItem(STORAGE_KEY_REQ, JSON.stringify(req))
    } catch {
      // ignore storage errors
    }

    // Invalidate stale result if new request payload does not match the evaluated result
    if (triageResult) {
      const newFp = computePatientFingerprint(req.patient)
      const resFp = computePatientFingerprint(triageResult.input_patient || triageResult.patient)
      if (newFp !== resFp) {
        setTriageResult(null)
        clearLiveEvents()
        try {
          sessionStorage.removeItem(STORAGE_KEY_RES)
        } catch {
          // ignore storage errors
        }
      }
    }
  }

  const evaluatePatient = async (req: TriageApiRequest): Promise<TriageResponse> => {
    setIsLoading(true)
    setError(null)
    // Clear previous result and live events immediately so stale results are never exposed during evaluation
    setTriageResult(null)
    clearLiveEvents()
    try {
      sessionStorage.removeItem(STORAGE_KEY_RES)
      sessionStorage.removeItem(STORAGE_KEY_EVENTS)
    } catch {
      // ignore storage errors
    }

    try {
      const payload: TriageApiRequest = {
        ...req,
        overrides: activeOverrides.length > 0 ? activeOverrides : req.overrides || [],
      }
      _setPatientRequest(payload)
      try {
        sessionStorage.setItem(STORAGE_KEY_REQ, JSON.stringify(payload))
      } catch {
        // ignore storage errors
      }

      let res: TriageResponse
      if (typeof api.streamTriage === 'function') {
        const receivedEvents: TriageLifecycleEvent[] = []
        try {
          res = await api.streamTriage(payload, (event) => {
            receivedEvents.push(event)
            setLiveEvents((prev) => [...prev, event])
          })
          try {
            sessionStorage.setItem(STORAGE_KEY_EVENTS, JSON.stringify(receivedEvents))
          } catch {
            // ignore storage errors
          }
        } catch (streamErr) {
          if (typeof api.runTriage === 'function') {
            res = await api.runTriage(payload)
          } else {
            throw streamErr
          }
        }
      } else {
        res = await api.runTriage(payload)
      }

      setTriageResult(res)
      try {
        sessionStorage.setItem(STORAGE_KEY_RES, JSON.stringify(res))
      } catch {
        // ignore storage errors
      }
      return res
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Triage evaluation failed'
      setError(msg)
      setTriageResult(null)
      throw err
    } finally {
      setIsLoading(false)
    }
  }

  const applyOverride = async (override: OverrideRecord): Promise<void> => {
    const updatedOverrides = [...activeOverrides, override]
    setActiveOverrides(updatedOverrides)
    if (patientRequest) {
      const payload: TriageApiRequest = {
        ...patientRequest,
        overrides: updatedOverrides,
      }
      setPatientRequest(payload)
      setIsLoading(true)
      try {
        let res: TriageResponse
        if (typeof api.streamTriage === 'function') {
          const receivedEvents: TriageLifecycleEvent[] = []
          try {
            res = await api.streamTriage(payload, (event) => {
              receivedEvents.push(event)
              setLiveEvents((prev) => [...prev, event])
            })
            try {
              sessionStorage.setItem(STORAGE_KEY_EVENTS, JSON.stringify(receivedEvents))
            } catch {
              // ignore storage errors
            }
          } catch {
            res = await api.runTriage(payload)
          }
        } else {
          res = await api.runTriage(payload)
        }
        setTriageResult(res)
        try {
          sessionStorage.setItem(STORAGE_KEY_RES, JSON.stringify(res))
        } catch {
          // ignore storage errors
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Override evaluation failed'
        setError(msg)
      } finally {
        setIsLoading(false)
      }
    }
  }

  const clearPatient = () => {
    setPatientRequest(null)
    setTriageResult(null)
    clearLiveEvents()
    setActiveOverrides([])
    setSelectedScenario(null)
    setIsDemoActive(false)
    setError(null)
    try {
      sessionStorage.removeItem(STORAGE_KEY_REQ)
      sessionStorage.removeItem(STORAGE_KEY_RES)
      sessionStorage.removeItem(STORAGE_KEY_DEMO)
      sessionStorage.removeItem(STORAGE_KEY_EVENTS)
    } catch {
      // ignore storage errors
    }
  }

  return (
    <TriageContext.Provider
      value={{
        patientRequest,
        triageResult,
        liveEvents,
        activeOverrides,
        selectedScenario,
        isDemoActive,
        isLoading,
        error,
        setPatientRequest,
        setSelectedScenario,
        loadDemoPatient,
        clearDemo,
        evaluatePatient,
        applyOverride,
        clearPatient,
        clearLiveEvents,
      }}
    >
      {children}
    </TriageContext.Provider>
  )
}

export const useTriage = (): TriageContextType => {
  const context = useContext(TriageContext)
  if (!context) {
    throw new Error('useTriage must be used within a TriageProvider')
  }
  return context
}
export default TriageProvider
