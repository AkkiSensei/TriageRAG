import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ScenarioSelector } from '@/features/intake/ScenarioSelector'
import { PatientIntakeForm } from '@/features/intake/PatientIntakeForm'
import { useTriage } from '@/context/TriageContext'
import type { TriageApiRequest, ScenarioDetail } from '@/lib/api'
import { Stethoscope, AlertCircle } from 'lucide-react'

export const IntakePage: React.FC = () => {
  const navigate = useNavigate()
  const {
    patientRequest,
    evaluatePatient,
    isLoading,
    error,
    selectedScenario,
    setSelectedScenario,
  } = useTriage()

  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(
    selectedScenario?.id ?? null
  )

  const handleSelectScenario = (scenario: ScenarioDetail, autoRun: boolean = true) => {
    setActiveScenarioId(scenario.id)
    setSelectedScenario(scenario)

    if (autoRun) {
      const p = scenario.patient
      const payload: TriageApiRequest = {
        patient: {
          ...p,
          pregnancy: p.sex === 'male' ? 'no' : p.pregnancy,
        },
        overrides: scenario.overrides || [],
      }
      evaluatePatient(payload)
        .then(() => {
          navigate('/report')
        })
        .catch((err) => {
          console.error('Scenario run error:', err)
        })
    }
  }

  const handleFormSubmit = async (req: TriageApiRequest) => {
    try {
      await evaluatePatient(req)
      navigate('/report')
    } catch (err) {
      console.error('Triage submission error:', err)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Station Header */}
      <div className="mb-6 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="flex h-2 w-2 rounded-full bg-teal-400" />
          <span className="text-xs font-mono uppercase tracking-widest text-teal-400 font-semibold">
            Emergency Triage Station
          </span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Patient Intake & Physiological Profile
        </h1>
        <p className="mt-1 text-xs sm:text-sm text-slate-400">
          Document presenting complaints, vital signs, and medication history for deterministic
          clinical decision support.
        </p>
      </div>

      {/* Preset Reference Scenarios */}
      <div className="mb-6">
        <ScenarioSelector
          onSelectScenario={handleSelectScenario}
          activeScenarioId={activeScenarioId}
          loadingScenarioId={isLoading ? activeScenarioId : null}
        />
      </div>

      {/* Pipeline Error Banner */}
      {error && (
        <div className="mb-6 flex items-center justify-between rounded-xl border border-red-900/80 bg-red-950/40 p-4 text-xs text-red-300">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="h-5 w-5 shrink-0 text-red-400" />
            <div>
              <span className="font-bold">Evaluation Error: </span>
              <span>{error}</span>
            </div>
          </div>
        </div>
      )}

      {/* Patient Intake Form */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 sm:p-6 shadow-xl">
        <div className="flex items-center gap-2 mb-4 text-slate-300 text-xs font-semibold uppercase tracking-wider">
          <Stethoscope className="h-4 w-4 text-teal-400" />
          <span>Clinical Intake Record</span>
        </div>
        <PatientIntakeForm
          onSubmit={handleFormSubmit}
          isLoading={isLoading}
          initialScenario={selectedScenario}
          existingRequest={patientRequest}
        />
      </div>
    </div>
  )
}
export default IntakePage
