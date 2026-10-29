import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTriage } from '@/context/TriageContext'
import { SafetyBanner } from '@/features/results/SafetyBanner'
import { ScoreCard } from '@/features/results/ScoreCard'
import { AlertsList } from '@/features/results/AlertsList'
import { SkippedChecksList } from '@/features/results/SkippedChecksList'
import { VerifiedPlanView } from '@/features/results/VerifiedPlanView'
import { RetrievalView } from '@/features/results/RetrievalView'
import { OverrideModal } from '@/features/results/OverrideModal'
import type { Alert, OverrideRecord } from '@/lib/api'
import {
  ArrowLeft,
  RotateCcw,
  ShieldCheck,
  User,
  Pill,
  ShieldAlert,
  Hash,
  Loader2,
  Scale,
} from 'lucide-react'

export const ReportPage: React.FC = () => {
  const navigate = useNavigate()
  const {
    patientRequest,
    triageResult,
    evaluatePatient,
    applyOverride,
    clearPatient,
    isLoading,
    error,
  } = useTriage()

  // Override modal state
  const [overrideModalOpen, setOverrideModalOpen] = useState(false)
  const [overrideRuleId, setOverrideRuleId] = useState('')
  const [overrideStepNumber, setOverrideStepNumber] = useState(1)

  const handleOpenOverride = (ruleId: string, stepNumber: number) => {
    setOverrideRuleId(ruleId)
    setOverrideStepNumber(stepNumber)
    setOverrideModalOpen(true)
  }

  const handleApplyOverride = async (override: OverrideRecord) => {
    await applyOverride(override)
  }

  const handleNewPatient = () => {
    clearPatient()
    navigate('/intake')
  }

  // Auto-evaluate if patientRequest exists but triageResult is not loaded yet
  React.useEffect(() => {
    if (!triageResult && patientRequest && !isLoading && !error) {
      evaluatePatient(patientRequest).catch((err: unknown) => {
        console.error('Auto-eval on ReportPage error:', err)
      })
    }
  }, [triageResult, patientRequest, isLoading, error, evaluatePatient])

  if (isLoading && !triageResult) {
    return (
      <div className="mx-auto flex min-h-[500px] max-w-5xl flex-col items-center justify-center p-8 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 shadow-soft mb-4">
          <Loader2 className="h-8 w-8 animate-spin text-teal-600 dark:text-teal-400" />
        </div>
        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
          Running Deterministic Clinical Engine...
        </h2>
        <p className="mt-1 text-xs sm:text-sm text-slate-500 dark:text-slate-400 max-w-md leading-relaxed">
          Evaluating contraindications, NEWS2/PEWS early warning scores, exact decimal dosing ceilings, and guideline citations.
        </p>
      </div>
    )
  }

  if (error && !triageResult) {
    return (
      <div className="mx-auto flex min-h-[450px] max-w-lg flex-col items-center justify-center p-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-rose-100 dark:bg-rose-950/70 border border-rose-200 dark:border-rose-800 text-rose-600 dark:text-rose-400 mb-4 shadow-soft">
          <ShieldAlert className="h-7 w-7" />
        </div>
        <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">Clinical Evaluation Failed</h3>
        <p className="mt-2 text-xs text-rose-950 dark:text-rose-200 leading-relaxed mb-6 max-w-md bg-rose-50 dark:bg-rose-950/50 p-4 rounded-2xl border border-rose-200 dark:border-rose-900/60 font-mono">
          {error}
        </p>
        <div className="flex items-center gap-3">
          {patientRequest && (
            <button
              type="button"
              onClick={() => evaluatePatient(patientRequest)}
              className="flex items-center gap-2 rounded-xl bg-teal-700 hover:bg-teal-800 px-5 py-2.5 text-xs font-bold text-white shadow-soft transition-all"
            >
              <RotateCcw className="h-4 w-4" />
              <span>Retry Evaluation</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => navigate('/intake')}
            className="flex items-center gap-2 rounded-xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] hover:bg-slate-50 dark:hover:bg-[#1a2d33] px-5 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-all shadow-soft-sm"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Intake Station</span>
          </button>
        </div>
      </div>
    )
  }

  if (!triageResult) {
    return (
      <div className="mx-auto flex min-h-[450px] max-w-md flex-col items-center justify-center p-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 mb-4 shadow-soft">
          <User className="h-7 w-7" />
        </div>
        <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">No Patient Evaluated</h3>
        <p className="mt-1.5 text-xs sm:text-sm text-slate-500 dark:text-slate-400 leading-relaxed mb-6">
          Please enter patient vital signs and medication history on the intake station first.
        </p>
        <button
          type="button"
          onClick={() => navigate('/intake')}
          className="flex items-center gap-2 rounded-xl bg-teal-700 hover:bg-teal-800 px-6 py-2.5 text-xs font-bold text-white shadow-soft transition-all"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Go to Patient Intake Station</span>
        </button>
      </div>
    )
  }

  const patient = patientRequest?.patient
  const engine = triageResult.engine
  const allAlerts: Alert[] = [
    ...(engine.baseline_alerts || []),
    ...(engine.plan_alerts || []),
  ]

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Top Action & Navigation Strip */}
      <div className="mb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#d9e8e6] dark:border-[#1e3840] pb-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/intake')}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] px-3.5 py-2 text-xs font-semibold text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-[#1a2d33] transition-colors shadow-soft-sm"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Edit Patient Intake</span>
          </button>
          <button
            type="button"
            onClick={handleNewPatient}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] px-3.5 py-2 text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-50 dark:hover:bg-[#1a2d33] transition-colors shadow-soft-sm"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>New Patient</span>
          </button>
        </div>

        <div className="flex items-center gap-2.5 text-xs font-mono text-slate-500 dark:text-slate-400">
          <span className="bg-teal-50 dark:bg-teal-950/60 text-teal-800 dark:text-teal-300 font-semibold px-2.5 py-0.5 rounded-full border border-teal-200 dark:border-teal-800">
            Ruleset {engine.ruleset_version}
          </span>
          <span>&bull;</span>
          <span>{engine.checks_run} deterministic rules checked</span>
        </div>
      </div>

      {/* Patient Wristband Strip */}
      {patient && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#d9e8e6] dark:border-[#1e3840] bg-white dark:bg-[#132226] px-5 py-3.5 text-xs shadow-soft">
          <div className="flex items-center gap-3.5 flex-wrap">
            <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-slate-100">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
                <User className="h-4 w-4" />
              </div>
              <span>
                {patient.age.value} {patient.age.unit} &bull; {patient.sex}
              </span>
            </div>
            <span className="text-slate-300 dark:text-slate-600">&bull;</span>
            <span className="text-slate-600 dark:text-slate-300 flex items-center gap-1 font-medium">
              <Scale className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500" />
              Weight: {patient.weight_kg.value ? `${patient.weight_kg.value} kg` : 'Unknown'}
            </span>
            <span className="text-slate-300 dark:text-slate-600">&bull;</span>
            <span className="text-teal-800 dark:text-teal-300 font-bold font-mono bg-teal-50 dark:bg-teal-950/60 px-2 py-0.5 rounded-md border border-teal-200 dark:border-teal-800">
              Syndrome: {patient.suspected_syndrome || 'Unspecified'}
            </span>
          </div>

          <div className="flex items-center gap-3 flex-wrap text-xs font-mono text-slate-600 dark:text-slate-400">
            <span className="flex items-center gap-1.5 bg-slate-50 dark:bg-[#0c1618] border border-slate-200 dark:border-[#1e3840] px-2.5 py-1 rounded-lg">
              <Pill className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
              {patient.medications?.length ?? 0} Home Meds
            </span>
            <span className="flex items-center gap-1.5 bg-slate-50 dark:bg-[#0c1618] border border-slate-200 dark:border-[#1e3840] px-2.5 py-1 rounded-lg">
              <ShieldAlert className="h-3.5 w-3.5 text-coral-500 dark:text-coral-400" />
              {patient.allergies?.length ?? 0} Allergies
            </span>
          </div>
        </div>
      )}

      {/* Error Banner if any */}
      {error && (
        <div className="mb-5 rounded-2xl border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/50 p-3.5 text-xs text-rose-900 dark:text-rose-200 shadow-soft-sm">
          {error}
        </div>
      )}

      {/* Main Report Body */}
      <div className="flex flex-col gap-6">
        {/* 1. Primary Verdict Banner (Static, zero animation) */}
        <SafetyBanner report={engine} />

        {/* 2. Physiological Score Card */}
        {engine.score && <ScoreCard score={engine.score} />}

        {/* 3. Drug Safety Alerts & Absolute Contraindications */}
        <AlertsList
          alerts={allAlerts}
          verifiedSteps={triageResult.verified_steps}
          onOverrideHighAlert={handleOpenOverride}
        />

        {/* 4. Recommended Clinical Protocol Plan */}
        {triageResult.verified_steps && triageResult.verified_steps.length > 0 && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-[#1e3840] pb-2">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-teal-700 dark:text-teal-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-100">
                  Recommended Protocol Orders ({triageResult.verified_steps.length} Steps)
                </h3>
              </div>
              <span className="text-[11px] text-teal-800 dark:text-teal-300 font-mono font-bold">
                Machine-Verified with Verbatim Citations
              </span>
            </div>
            <VerifiedPlanView steps={triageResult.verified_steps} />
          </div>
        )}

        {/* 5. Unverified Checks / Missing Data (Fail-Closed) */}
        {engine.checks_skipped && engine.checks_skipped.length > 0 && (
          <SkippedChecksList
            skippedChecks={engine.checks_skipped}
            onFixInIntake={() => navigate('/intake')}
          />
        )}

        {/* 6. Protocol Retrieval Evidence */}
        <RetrievalView triage={triageResult} />

        {/* 7. Cryptographic Audit Chain Seal */}
        {triageResult.audit_hash && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-4 text-xs font-mono text-slate-500 dark:text-slate-400 shadow-soft">
            <div className="flex items-center gap-2">
              <Hash className="h-4 w-4 text-teal-700 dark:text-teal-400 shrink-0" />
              <span className="text-slate-900 dark:text-slate-100 font-bold">SHA-256 Merkle Audit Seal:</span>
            </div>
            <span className="truncate max-w-full sm:max-w-md text-teal-700 dark:text-teal-300 font-bold font-mono bg-teal-50 dark:bg-teal-950/60 px-2.5 py-1 rounded-lg border border-teal-200 dark:border-teal-800 select-all">
              {triageResult.audit_hash}
            </span>
          </div>
        )}
      </div>

      {/* Clinician Justification Modal for HIGH severity alerts */}
      <OverrideModal
        isOpen={overrideModalOpen}
        ruleId={overrideRuleId}
        stepNumber={overrideStepNumber}
        onClose={() => setOverrideModalOpen(false)}
        onSubmit={handleApplyOverride}
      />
    </div>
  )
}

export default ReportPage
