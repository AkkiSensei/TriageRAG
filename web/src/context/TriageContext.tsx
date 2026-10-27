import React, { createContext, useContext, useState } from 'react'
import {
  api,
  type TriageApiRequest,
  type TriageResponse,
  type OverrideRecord,
  type ScenarioDetail,
} from '@/lib/api'

interface TriageContextType {
  patientRequest: TriageApiRequest | null
  triageResult: TriageResponse | null
  activeOverrides: OverrideRecord[]
  selectedScenario: ScenarioDetail | null
  isLoading: boolean
  error: string | null
  setPatientRequest: (req: TriageApiRequest | null) => void
  setSelectedScenario: (scenario: ScenarioDetail | null) => void
  evaluatePatient: (req: TriageApiRequest) => Promise<TriageResponse>
  applyOverride: (override: OverrideRecord) => Promise<void>
  clearPatient: () => void
}

const TriageContext = createContext<TriageContextType | undefined>(undefined)

const STORAGE_KEY_REQ = 'triagerag_patient_request'
const STORAGE_KEY_RES = 'triagerag_triage_result'

export const TriageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [patientRequest, setPatientRequest] = useState<TriageApiRequest | null>(() => {
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
      const saved = sessionStorage.getItem(STORAGE_KEY_RES)
      return saved ? JSON.parse(saved) : null
    } catch {
      return null
    }
  })

  const [activeOverrides, setActiveOverrides] = useState<OverrideRecord[]>([])
  const [selectedScenario, setSelectedScenario] = useState<ScenarioDetail | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const evaluatePatient = async (req: TriageApiRequest): Promise<TriageResponse> => {
    setIsLoading(true)
    setError(null)
    try {
      const payload: TriageApiRequest = {
        ...req,
        overrides: activeOverrides.length > 0 ? activeOverrides : req.overrides || [],
      }
      setPatientRequest(payload)
      try {
        sessionStorage.setItem(STORAGE_KEY_REQ, JSON.stringify(payload))
      } catch {
        // ignore storage errors
      }

      const res = await api.runTriage(payload)
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
        const res = await api.runTriage(payload)
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
    setActiveOverrides([])
    setSelectedScenario(null)
    setError(null)
    try {
      sessionStorage.removeItem(STORAGE_KEY_REQ)
      sessionStorage.removeItem(STORAGE_KEY_RES)
    } catch {
      // ignore storage errors
    }
  }

  return (
    <TriageContext.Provider
      value={{
        patientRequest,
        triageResult,
        activeOverrides,
        selectedScenario,
        isLoading,
        error,
        setPatientRequest,
        setSelectedScenario,
        evaluatePatient,
        applyOverride,
        clearPatient,
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
