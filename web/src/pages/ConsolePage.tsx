import React, { useState } from 'react'
import { PatientIntakeForm } from '@/features/intake/PatientIntakeForm'
import { ResultsPane } from '@/features/results/ResultsPane'
import { useMutation } from '@tanstack/react-query'
import { api, type TriageApiRequest, type TriageResponse } from '@/lib/api'
import { SplitText, BlurText, ShinyText } from '@/components/reactbits'
import { AlertCircle } from 'lucide-react'

export const ConsolePage: React.FC = () => {
  const [triageResult, setTriageResult] = useState<TriageResponse | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)

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
    mutation.mutate(req)
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header section with React Bits animations */}
      <div className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="flex h-2 w-2 rounded-full bg-teal-400" />
            <ShinyText text="DETERMINISTIC CLINICAL DECISION SUPPORT" className="text-xs uppercase tracking-widest" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            <SplitText text="Emergency Triage Console" />
          </h1>
          <div className="mt-1 text-sm text-slate-400">
            <BlurText text="Code decides; the LLM explains. Deterministic early warning scores, drug safety contraindications, and verified protocol plans." />
          </div>
        </div>
      </div>

      {lastError && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-red-900/80 bg-red-950/40 p-4 text-xs text-red-300">
          <AlertCircle className="h-5 w-5 shrink-0 text-red-400" />
          <div>
            <span className="font-bold">Execution Error: </span>
            {lastError}
          </div>
        </div>
      )}

      {/* Main console layout grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Intake Stepper & Form */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          <PatientIntakeForm onSubmit={handleSubmit} isLoading={mutation.isPending} />
        </div>

        {/* Right Column: Static Results Pane */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          <ResultsPane
            triage={triageResult}
            isLoading={mutation.isPending}
            onOverrideHighAlert={(ruleId) => {
              alert(`Override requested for HIGH alert: ${ruleId}. Recorded overrides are supported in Gate F4.`)
            }}
          />
        </div>
      </div>
    </div>
  )
}
