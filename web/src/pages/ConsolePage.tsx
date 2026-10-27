import React, { useState, useEffect, useRef } from 'react'
import { PatientIntakeForm } from '@/features/intake/PatientIntakeForm'
import { ScenarioSelector } from '@/features/intake/ScenarioSelector'
import { ResultsPane } from '@/features/results/ResultsPane'
import { OverrideModal } from '@/features/results/OverrideModal'
import { useMutation } from '@tanstack/react-query'
import {
  api,
  type TriageApiRequest,
  type TriageResponse,
  type OverrideRecord,
  type ScenarioDetail,
} from '@/lib/api'
import { AlertCircle } from 'lucide-react'

export const ConsolePage: React.FC = () => {
  const [triageResult, setTriageResult] = useState<TriageResponse | null>(null)
  const [lastRequest, setLastRequest] = useState<TriageApiRequest | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)

  // Active scenario tracking for highlight
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>('BLOCK')
  const [selectedScenarioDetail, setSelectedScenarioDetail] = useState<ScenarioDetail | null>(null)

  // Override modal state
  const [overrideModalOpen, setOverrideModalOpen] = useState(false)
  const [pendingOverrideRuleId, setPendingOverrideRuleId] = useState<string>('')
  const [activeOverrides, setActiveOverrides] = useState<OverrideRecord[]>([])

  const hasAutoLoadedRef = useRef(false)

  const mutation = useMutation({
    mutationFn: (req: TriageApiRequest) => api.runTriage(req),
    onSuccess: (data) => {
      setTriageResult(data)
      setLastError(null)
    },
    onError: (err: Error) => {
      setLastError(err?.message || 'Failed to execute triage analysis')
    },
  })

  const handleSubmit = (req: TriageApiRequest) => {
    const payload: TriageApiRequest = {
      ...req,
      overrides: activeOverrides.length > 0 ? activeOverrides : req.overrides,
    }
    setLastRequest(payload)
    mutation.mutate(payload)
  }

  // Handle 1-click scenario showcase selection
  const handleScenarioSelect = (scenario: ScenarioDetail, autoRun: boolean = true) => {
    setActiveScenarioId(scenario.id)
    setSelectedScenarioDetail(scenario)

    if (autoRun) {
      // Build immediate request from the loaded scenario patient
      const p = scenario.patient
      const payload: TriageApiRequest = {
        patient: {
          ...p,
          // Enforce male pregnancy invariant
          pregnancy: p.sex === 'male' ? 'no' : p.pregnancy,
        },
        overrides: scenario.overrides || [],
      }
      setLastRequest(payload)
      mutation.mutate(payload)
    }
  }

  // Auto-load default BLOCK scenario on initial page mount so the page is immediately alive
  useEffect(() => {
    if (!hasAutoLoadedRef.current) {
      hasAutoLoadedRef.current = true
      api
        .getScenario('BLOCK')
        .then((scenario) => {
          setActiveScenarioId(scenario.id)
          setSelectedScenarioDetail(scenario)
          const p = scenario.patient
          const payload: TriageApiRequest = {
            patient: {
              ...p,
              pregnancy: p.sex === 'male' ? 'no' : p.pregnancy,
            },
            overrides: scenario.overrides || [],
          }
          setLastRequest(payload)
          mutation.mutate(payload)
        })
        .catch((err) => {
          console.warn('Initial scenario auto-load deferred:', err)
        })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleOpenOverride = (ruleId: string) => {
    setPendingOverrideRuleId(ruleId)
    setOverrideModalOpen(true)
  }

  const handleApplyOverride = (override: OverrideRecord) => {
    const updated = [...activeOverrides, override]
    setActiveOverrides(updated)
    if (lastRequest) {
      const payload: TriageApiRequest = {
        ...lastRequest,
        overrides: updated,
      }
      setLastRequest(payload)
      mutation.mutate(payload)
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Sleek Hero Header */}
      <div className="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="flex h-2 w-2 rounded-full bg-teal-400 animate-pulse" />
            <span className="text-xs font-mono uppercase tracking-widest text-teal-400 font-semibold">
              Clinical Decision Support
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Emergency Triage Console
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-400 max-w-2xl">
            Code decides; the LLM explains. Deterministic physiological scores, drug contraindication
            detection, and machine-verified protocol drafting.
          </p>
        </div>

        {activeOverrides.length > 0 && (
          <div className="flex items-center gap-2 rounded-lg border border-amber-900/60 bg-amber-950/40 px-3 py-1.5 text-xs text-amber-300 font-mono">
            <span>Recorded Overrides: {activeOverrides.length}</span>
            <button
              type="button"
              onClick={() => {
                setActiveOverrides([])
                if (lastRequest) {
                  const payload = { ...lastRequest, overrides: [] }
                  setLastRequest(payload)
                  mutation.mutate(payload)
                }
              }}
              className="text-[10px] underline text-amber-400 hover:text-amber-200"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* 1-Click Golden Showcase Bar (Prominently Placed) */}
      <div className="mb-6">
        <ScenarioSelector
          onSelectScenario={handleScenarioSelect}
          activeScenarioId={activeScenarioId}
          loadingScenarioId={mutation.isPending ? activeScenarioId : null}
        />
      </div>

      {lastError && (
        <div className="mb-6 flex items-center justify-between rounded-xl border border-red-900/80 bg-red-950/40 p-4 text-xs text-red-300">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="h-5 w-5 shrink-0 text-red-400" />
            <div>
              <span className="font-bold">Pipeline Error: </span>
              <span>{lastError}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setLastError(null)}
            className="text-red-400 hover:text-red-200 font-mono text-[11px]"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 2-Column Clinical Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Patient Intake Form */}
        <div className="lg:col-span-5 xl:col-span-5">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 sm:p-5 shadow-xl backdrop-blur-sm">
            <PatientIntakeForm
              onSubmit={handleSubmit}
              isLoading={mutation.isPending}
              initialScenario={selectedScenarioDetail}
            />
          </div>
        </div>

        {/* Right Column: Live Clinical Decision Report */}
        <div className="lg:col-span-7 xl:col-span-7">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 sm:p-6 shadow-xl backdrop-blur-sm">
            <ResultsPane
              triage={triageResult}
              isLoading={mutation.isPending}
              onOverrideHighAlert={handleOpenOverride}
            />
          </div>
        </div>
      </div>

      {/* Clinician Justification Modal for HIGH alerts */}
      <OverrideModal
        isOpen={overrideModalOpen}
        ruleId={pendingOverrideRuleId}
        stepNumber={1}
        onClose={() => setOverrideModalOpen(false)}
        onSubmit={handleApplyOverride}
      />
    </div>
  )
}
export default ConsolePage
