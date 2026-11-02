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
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8 space-y-6">
      {/* Station Header */}
      <div className="flex flex-col gap-2 rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 sm:p-6 shadow-soft">
        <div className="flex items-center gap-2">
          <span className="flex h-2.5 w-2.5 rounded-full bg-teal-600 animate-pulse" />
          <span className="text-xs uppercase tracking-wider text-teal-800 dark:text-teal-300 font-bold">
            Hospital Emergency Support
          </span>
          <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-teal-50 dark:bg-teal-950/80 text-teal-800 dark:text-teal-300 font-semibold border border-teal-200 dark:border-teal-800">
            Ward &amp; Clinic
          </span>
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-3xl">
          Enter Patient Details
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-2xl leading-relaxed">
          Fill in the patient&apos;s age, vital signs, and current medicines. The system will check all safety rules,
          verify drug interactions, and display clear step-by-step instructions.
        </p>
      </div>

      {/* Pipeline Error Banner */}
      {error && (
        <div className="flex items-center justify-between rounded-2xl border border-rose-200 bg-rose-50/90 p-4 text-xs text-rose-900 shadow-soft-sm">
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
      <div className="rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 sm:p-7 shadow-soft">
        <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-700 pb-3.5 mb-5">
          <div className="flex items-center gap-2.5 text-slate-900 dark:text-white text-xs font-bold uppercase tracking-wider">
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/80 text-teal-700 dark:text-teal-300">
              <Stethoscope className="h-4 w-4" />
            </div>
            <span>Patient Intake Form</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <ShieldAlert className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
            <span>Automatic Safety Check</span>
          </div>
        </div>

        <PatientIntakeForm
          onSubmit={handleFormSubmit}
          isLoading={isLoading}
          existingRequest={patientRequest}
          errorMessage={error}
        />
      </div>
    </div>
  )
}

export default IntakePage
