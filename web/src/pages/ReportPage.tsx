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
        <Loader2 className="h-10 w-10 animate-spin text-[#2D6A4F] mb-4" />
        <h2 className="text-base font-bold text-[#1A2421]">
          Running Deterministic Clinical Engine...
        </h2>
        <p className="mt-1 text-xs text-[#5C6B64]">
          Evaluating contraindications, NEWS2 score, formulary limits, and protocol citations.
        </p>
      </div>
    )
  }

  if (error && !triageResult) {
    return (
      <div className="mx-auto flex min-h-[450px] max-w-lg flex-col items-center justify-center p-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 border border-red-300 text-red-600 mb-4">
          <ShieldAlert className="h-6 w-6" />
        </div>
        <h3 className="text-base font-bold text-[#1A2421]">Clinical Evaluation Failed</h3>
        <p className="mt-1.5 text-xs text-red-900 leading-relaxed mb-5 max-w-md bg-red-50 p-3 rounded-xl border border-red-200 font-mono">
          {error}
        </p>
        <div className="flex items-center gap-3">
          {patientRequest && (
            <button
              type="button"
              onClick={() => evaluatePatient(patientRequest)}
              className="flex items-center gap-2 rounded-lg bg-[#2D6A4F] hover:bg-[#1B4D39] px-4 py-2 text-xs font-bold text-white shadow-xs transition-colors"
            >
              <RotateCcw className="h-4 w-4" />
              <span>Retry Evaluation</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => navigate('/intake')}
            className="flex items-center gap-2 rounded-lg border border-[#E1E7E1] bg-white hover:bg-[#EEF3EE] px-4 py-2 text-xs font-medium text-[#1A2421] transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Patient Intake</span>
          </button>
        </div>
      </div>
    )
  }

  if (!triageResult) {
    return (
      <div className="mx-auto flex min-h-[450px] max-w-md flex-col items-center justify-center p-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#EEF3EE] text-[#5C6B64] mb-4">
          <User className="h-6 w-6" />
        </div>
        <h3 className="text-base font-bold text-[#1A2421]">No Patient Evaluated</h3>
        <p className="mt-1.5 text-xs text-[#5C6B64] leading-relaxed mb-5">
          Please enter patient vital signs and medication history on the intake station first.
        </p>
        <button
          type="button"
          onClick={() => navigate('/intake')}
          className="flex items-center gap-2 rounded-lg bg-[#2D6A4F] hover:bg-[#1B4D39] px-4 py-2 text-xs font-bold text-white shadow-xs transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Go to Patient Intake</span>
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
      <div className="mb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E1E7E1] pb-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/intake')}
            className="flex items-center gap-1.5 rounded-lg border border-[#E1E7E1] bg-white px-3 py-1.5 text-xs font-semibold text-[#1A2421] hover:bg-[#EEF3EE] transition-colors shadow-xs"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Edit Patient Intake</span>
          </button>
          <button
            type="button"
            onClick={handleNewPatient}
            className="flex items-center gap-1.5 rounded-lg border border-[#E1E7E1] bg-white px-3 py-1.5 text-xs font-medium text-[#5C6B64] hover:text-[#1A2421] hover:bg-[#EEF3EE] transition-colors shadow-xs"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>New Patient</span>
          </button>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-[#5C6B64]">
          <span>Ruleset {engine.ruleset_version}</span>
          <span>•</span>
          <span>{engine.checks_run} rules checked</span>
        </div>
      </div>

      {/* Patient Wristband Strip */}
      {patient && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E1E7E1] bg-white px-4 py-3 text-xs shadow-xs">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="flex items-center gap-1.5 font-bold text-[#1A2421]">
              <User className="h-4 w-4 text-[#2D6A4F]" />
              {patient.age.value} {patient.age.unit} {patient.sex}
            </span>
            <span className="text-[#8A9991]">•</span>
            <span className="text-[#5C6B64]">
              Weight: {patient.weight_kg.value ? `${patient.weight_kg.value} kg` : 'Unknown'}
            </span>
            <span className="text-[#8A9991]">•</span>
            <span className="text-[#2D6A4F] font-bold font-mono">
              Syndrome: {patient.suspected_syndrome || 'Unspecified'}
            </span>
          </div>

          <div className="flex items-center gap-4 flex-wrap text-[11px] font-mono text-[#5C6B64]">
            <span className="flex items-center gap-1">
              <Pill className="h-3.5 w-3.5 text-[#5C6B64]" />
              {patient.medications?.length ?? 0} Home Meds
            </span>
            <span className="flex items-center gap-1">
              <ShieldAlert className="h-3.5 w-3.5 text-[#5C6B64]" />
              {patient.allergies?.length ?? 0} Allergies
            </span>
          </div>
        </div>
      )}

      {/* Error Banner if any */}
      {error && (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800 shadow-xs">
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
            <div className="flex items-center justify-between border-b border-[#E1E7E1] pb-2">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-[#2D6A4F]" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#1A2421]">
                  Recommended Protocol Orders ({triageResult.verified_steps.length} Steps)
                </h3>
              </div>
              <span className="text-[10px] text-[#2D6A4F] font-mono font-bold">
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
          <div className="flex items-center justify-between rounded-xl border border-[#E1E7E1] bg-white p-3.5 text-[11px] font-mono text-[#5C6B64] shadow-xs">
            <div className="flex items-center gap-2">
              <Hash className="h-3.5 w-3.5 text-[#2D6A4F]" />
              <span className="text-[#1A2421] font-semibold">Audit Record SHA-256 Seal:</span>
            </div>
            <span className="truncate max-w-[280px] sm:max-w-md text-[#2D6A4F] font-bold font-mono select-all">
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

