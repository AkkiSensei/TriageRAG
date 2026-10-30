import React from 'react'
import { useNavigate } from 'react-router-dom'
import { PatientIntakeForm } from '@/features/intake/PatientIntakeForm'
import { useTriage } from '@/context/TriageContext'
import type { TriageApiRequest } from '@/lib/api'
import { Stethoscope, AlertCircle, ShieldAlert } from 'lucide-react'

export const IntakePage: React.FC = () => {
  const navigate = useNavigate()
  const {
    patientRequest,
    evaluatePatient,
    isLoading,
    error,
    selectedScenario,
  } = useTriage()

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
      <div className="mb-6 flex flex-col gap-2 rounded-3xl border border-[#d9e8e6] bg-gradient-to-r from-white via-teal-50/30 to-white p-5 sm:p-6 shadow-soft">
        <div className="flex items-center gap-2">
          <span className="flex h-2.5 w-2.5 rounded-full bg-teal-600 animate-pulse" />
          <span className="text-xs font-mono uppercase tracking-widest text-teal-800 font-bold">
            Emergency Triage Station
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-teal-100 text-teal-900 font-semibold">
            Pass 1 Intake
          </span>
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          Patient Intake &amp; Physiological Profile
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 max-w-2xl leading-relaxed">
          Record measured or estimated vital signs, medication history, and acute complaints.
          Deterministic rules will check contraindications and early warning scores before guideline retrieval.
        </p>
      </div>

      {/* Pipeline Error Banner */}
      {error && (
        <div className="mb-6 flex items-center justify-between rounded-2xl border border-rose-200 bg-rose-50/90 p-4 text-xs text-rose-900 shadow-soft-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-rose-100 text-rose-600">
              <AlertCircle className="h-5 w-5" />
            </div>
            <div>
              <span className="font-bold">Evaluation Engine Error: </span>
              <span className="font-mono">{error}</span>
            </div>
          </div>
        </div>
      )}

      {/* Patient Intake Form */}
      <div className="rounded-3xl border border-[#d9e8e6] bg-white p-5 sm:p-7 shadow-soft">
        <div className="flex items-center justify-between border-b border-[#d9e8e6] pb-3.5 mb-5">
          <div className="flex items-center gap-2.5 text-slate-900 text-xs font-bold uppercase tracking-wider">
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
              <Stethoscope className="h-4 w-4" />
            </div>
            <span>Clinical Data Capture</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-500">
            <ShieldAlert className="h-3.5 w-3.5 text-teal-600" />
            <span>Strict Decimal Math &bull; Fail-Closed</span>
          </div>
        </div>

        <PatientIntakeForm
          onSubmit={handleFormSubmit}
          isLoading={isLoading}
          initialScenario={selectedScenario}
          existingRequest={patientRequest}
          errorMessage={error}
        />
      </div>
    </div>
  )
}

export default IntakePage
