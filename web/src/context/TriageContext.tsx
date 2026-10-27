import React, { createContext, useContext, useState, useEffect } from 'react'
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

export const TriageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [patientRequest, setPatientRequest] = useState<TriageApiRequest | null>(null)
  const [triageResult, setTriageResult] = useState<TriageResponse | null>(null)
  const [activeOverrides, setActiveOverrides] = useState<OverrideRecord[]>([])
  const [selectedScenario, setSelectedScenario] = useState<ScenarioDetail | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Pre-load default BLOCK scenario on first mount so demo is always ready
  useEffect(() => {
    let mounted = true
    api
      .getScenario('BLOCK')
      .then((scenario) => {
        if (!mounted) return
        setSelectedScenario(scenario)
        const p = scenario.patient
        const initialReq: TriageApiRequest = {
          patient: {
            ...p,
            pregnancy: p.sex === 'male' ? 'no' : p.pregnancy,
          },
          overrides: scenario.overrides || [],
        }
        setPatientRequest(initialReq)
      })
      .catch((err) => {
        console.warn('Initial default scenario loading deferred:', err)
      })
    return () => {
      mounted = false
    }
  }, [])

  const evaluatePatient = async (req: TriageApiRequest): Promise<TriageResponse> => {
    setIsLoading(true)
    setError(null)
    try {
      const payload: TriageApiRequest = {
        ...req,
        overrides: activeOverrides.length > 0 ? activeOverrides : req.overrides || [],
      }
      setPatientRequest(payload)
      const res = await api.runTriage(payload)
      setTriageResult(res)
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
