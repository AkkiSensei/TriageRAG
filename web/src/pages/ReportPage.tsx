import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTriage, computePatientFingerprint } from '@/context/TriageContext'
import { OverrideModal } from '@/features/results/OverrideModal'
import { LiveProcessPanel } from '@/features/execution/LiveProcessPanel'
import type { OverrideRecord } from '@/lib/api'
import {
  ArrowLeft,
  RotateCcw,
  CheckCircle2,
  AlertOctagon,
  AlertTriangle,
  AlertCircle,
  User,
  Scale,
  Pill,
  ShieldAlert,
  Loader2,
  Clock,
} from 'lucide-react'

export const ReportPage: React.FC = () => {
  const navigate = useNavigate()
  const {
    patientRequest,
    triageResult,
    evaluatePatient,
    applyOverride,
    clearPatient,
    liveEvents,
    isLoading,
    error,
  } = useTriage()

  // Override modal state for HIGH severity alerts
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

  // Auto-evaluate if patientRequest exists but triageResult is not loaded yet or is mismatched (stale)
  React.useEffect(() => {
    if (patientRequest && !isLoading && !error) {
      if (!triageResult) {
        evaluatePatient(patientRequest).catch((err: unknown) => {
          console.error('Auto-eval on ReportPage error:', err)
        })
      } else {
        const reqFp = computePatientFingerprint(patientRequest.patient)
        const resFp = computePatientFingerprint(triageResult.input_patient || triageResult.patient)
        if (reqFp !== resFp) {
          evaluatePatient(patientRequest).catch((err: unknown) => {
            console.error('Auto-eval on ReportPage error (mismatched stale result):', err)
          })
        }
      }
    }
  }, [triageResult, patientRequest, isLoading, error, evaluatePatient])

  // Guard against displaying a mismatched stale result during state transition
  const isMismatched = Boolean(
    triageResult &&
      patientRequest &&
      computePatientFingerprint(patientRequest.patient) !==
        computePatientFingerprint(triageResult.input_patient || triageResult.patient)
  )

  // Never display an existing or stale result while a request is in flight or mismatched
  if (isLoading || isMismatched || !triageResult) {
    return (
      <div className="mx-auto flex min-h-[500px] max-w-4xl flex-col items-center justify-center p-8 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 shadow-sm mb-4">
          <Loader2 className="h-8 w-8 animate-spin text-teal-600 dark:text-teal-400" />
        </div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-white">
          Checking Safety Rules &amp; Preparing Steps...
        </h2>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400 max-w-md leading-relaxed">
          Checking medicine combinations, age-appropriate doses, and emergency care steps.
        </p>
      </div>
    )
  }

  if (error && !triageResult) {
    return (
      <div className="mx-auto flex min-h-[450px] max-w-lg flex-col items-center justify-center p-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-rose-100 dark:bg-rose-950/70 border border-rose-200 dark:border-rose-800 text-rose-600 dark:text-rose-400 mb-4 shadow-sm">
          <ShieldAlert className="h-7 w-7" />
        </div>
        <h3 className="text-xl font-bold text-slate-900 dark:text-white">Unable to Check Safety</h3>
        <p className="mt-2 text-xs text-rose-900 dark:text-rose-200 leading-relaxed mb-6 max-w-md bg-rose-50 dark:bg-rose-950/50 p-4 rounded-2xl border border-rose-200 dark:border-rose-900/60 font-mono">
          {error}
        </p>
        <div className="flex items-center gap-3">
          {patientRequest && (
            <button
              type="button"
              onClick={() => evaluatePatient(patientRequest)}
              className="flex items-center gap-2 rounded-xl bg-teal-600 hover:bg-teal-700 px-5 py-2.5 text-xs font-bold text-white shadow-sm transition-all cursor-pointer"
            >
              <RotateCcw className="h-4 w-4" />
              <span>Retry</span>
            </button>
          )}
          <button
            type="button"
            onClick={() => navigate('/intake')}
            className="flex items-center gap-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-5 py-2.5 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-all shadow-sm cursor-pointer"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Patient Details</span>
          </button>
        </div>
      </div>
    )
  }

  if (!triageResult) {
    return (
      <div className="mx-auto flex min-h-[450px] max-w-md flex-col items-center justify-center p-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 mb-4 shadow-sm">
          <User className="h-7 w-7" />
        </div>
        <h3 className="text-xl font-bold text-slate-900 dark:text-white">No Patient Selected</h3>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400 leading-relaxed mb-6">
          Please enter patient vital signs and medicine details first.
        </p>
        <button
          type="button"
          onClick={() => navigate('/intake')}
          className="flex items-center gap-2 rounded-xl bg-teal-600 hover:bg-teal-700 px-6 py-2.5 text-xs font-bold text-white shadow-sm transition-all cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Enter Patient Details</span>
        </button>
      </div>
    )
  }

  const patient = triageResult?.patient || patientRequest?.patient
  const engine = triageResult.engine
  const verdict = engine.verdict
  const isBlock = verdict === 'BLOCKED'
  const isUnverified = verdict === 'UNVERIFIED'
  const isDoctorReview = verdict === 'CHECKED_ALERTS'
  const isAllClear = verdict === 'CHECKED_CLEAR'

  // Friendly human readable syndrome name
  const getSyndromeLabel = (code?: string | null) => {
    switch (code) {
      case 'chest_pain':
        return 'Severe Chest Pain (Possible Heart Attack)'
      case 'anaphylaxis':
        return 'Severe Allergic Reaction'
      case 'severe_asthma':
        return 'Severe Asthma Attack'
      case 'hypoglycemia':
        return 'Low Blood Sugar'
      case 'paediatric_sepsis':
        return 'Severe Infection / Sepsis'
      case 'altered_mental_status':
        return 'Confusion or Drowsiness'
      default:
        return 'General Health Check'
    }
  }

  // Format timestamp to Indian Standard Time (DD/MM/YYYY)
  const formatIndianDateTime = (isoString?: string | null) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      const day = String(d.getDate()).padStart(2, '0')
      const month = String(d.getMonth() + 1).padStart(2, '0')
      const year = d.getFullYear()
      const hours = String(d.getHours()).padStart(2, '0')
      const minutes = String(d.getMinutes()).padStart(2, '0')
      return `${day}/${month}/${year}, ${hours}:${minutes} IST`
    } catch {
      return isoString
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Top Navigation & Patient Summary Strip */}
      <div className="mb-6 flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => navigate('/intake')}
              className="flex items-center gap-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700/60 transition-colors shadow-sm cursor-pointer"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Back to Patient Details</span>
            </button>
            <button
              type="button"
              onClick={handleNewPatient}
              className="flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800 px-3.5 py-2 text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors shadow-sm cursor-pointer"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>New Patient</span>
            </button>
          </div>

          <span className="text-xs font-semibold text-teal-700 dark:text-teal-400 bg-teal-50 dark:bg-teal-950/60 px-3 py-1 rounded-full border border-teal-200 dark:border-teal-800">
            Emergency Care Instructions
          </span>
        </div>

        {/* Patient Wristband Strip */}
        {patient && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-5 py-3.5 text-xs shadow-sm">
            <div className="flex items-center gap-3.5 flex-wrap">
              <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-white">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
                  <User className="h-4 w-4" />
                </div>
                <span>
                  {patient.age.value} {patient.age.unit} &bull; {patient.sex}
                </span>
              </div>
              <span className="text-slate-300 dark:text-slate-700">&bull;</span>
              <span className="text-slate-600 dark:text-slate-300 flex items-center gap-1">
                <Scale className="h-3.5 w-3.5 text-slate-400" />
                Weight: {patient?.weight_kg?.value !== null && patient?.weight_kg?.value !== undefined ? `${patient.weight_kg.value} kg` : 'Unknown'}
              </span>
              <span className="text-slate-300 dark:text-slate-700">&bull;</span>
              <span className="text-teal-800 dark:text-teal-300 font-bold bg-teal-50 dark:bg-teal-950/60 px-2.5 py-0.5 rounded-md border border-teal-200 dark:border-teal-800">
                {getSyndromeLabel(patient.suspected_syndrome)}
              </span>
              {patient.assessed_at && (
                <>
                  <span className="text-slate-300 dark:text-slate-700">&bull;</span>
                  <span className="text-slate-500 dark:text-slate-400 flex items-center gap-1 font-mono text-[11px]">
                    <Clock className="h-3 w-3 text-slate-400" />
                    {formatIndianDateTime(patient.assessed_at)}
                  </span>
                </>
              )}
            </div>

            <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
              <span className="flex items-center gap-1 bg-slate-50 dark:bg-slate-800 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700">
                <Pill className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
                {patient.medications?.length ?? 0} Home Meds
              </span>
              <span className="flex items-center gap-1 bg-slate-50 dark:bg-slate-800 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700">
                <ShieldAlert className="h-3.5 w-3.5 text-rose-500" />
                {patient.allergies?.length ?? 0} Allergies
              </span>
            </div>

            {patient.chief_complaint_untrusted && (
              <div className="w-full mt-2 pt-2.5 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold text-[10px] uppercase tracking-wider text-amber-800 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/60 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-800">
                    Untrusted Chief Complaint (Quarantined &bull; Rule R7)
                  </span>
                  <span className="text-slate-700 dark:text-slate-300 italic">
                    &ldquo;{patient.chief_complaint_untrusted}&rdquo;
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Main Status Banner */}
      <div className="mb-6">
        {isBlock && (
          <div className="rounded-2xl border-2 border-rose-400 bg-rose-50 dark:bg-rose-950/70 dark:border-rose-700 p-5 shadow-sm">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-rose-600 text-white shadow-md">
                <AlertOctagon className="h-7 w-7" />
              </div>
              <div className="flex-1">
                <span className="inline-block text-[11px] font-bold uppercase tracking-wider text-rose-800 dark:text-rose-200 bg-rose-100 dark:bg-rose-900/60 px-2.5 py-0.5 rounded-full mb-1">
                  DANGER / STOP
                </span>
                <h2 className="text-lg sm:text-xl font-extrabold text-rose-950 dark:text-rose-100">
                  STOP: DO NOT GIVE THIS MEDICINE
                </h2>
                <p className="mt-1 text-xs sm:text-sm text-rose-900/90 dark:text-rose-200 leading-relaxed font-medium">
                  A dangerous medicine combination was detected. Stop immediately, do not administer contraindicated medicine, and inform the doctor on duty.
                </p>
              </div>
            </div>
          </div>
        )}

        {isUnverified && (
          <div className="rounded-2xl border-2 border-amber-400 bg-amber-50 dark:bg-amber-950/70 dark:border-amber-700 p-5 shadow-sm">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-amber-500 text-white shadow-md">
                <AlertCircle className="h-7 w-7" />
              </div>
              <div className="flex-1">
                <span className="inline-block text-[11px] font-bold uppercase tracking-wider text-amber-900 dark:text-amber-200 bg-amber-100 dark:bg-amber-900/60 px-2.5 py-0.5 rounded-full mb-1">
                  INCOMPLETE DETAILS
                </span>
                <h2 className="text-lg sm:text-xl font-extrabold text-amber-950 dark:text-amber-100">
                  CANNOT CONFIRM SAFETY (MISSING INFORMATION)
                </h2>
                <p className="mt-1 text-xs sm:text-sm text-amber-900/90 dark:text-amber-200 leading-relaxed font-medium">
                  Some vital signs or medicine history are not recorded. Safety cannot be checked until missing items are entered.
                </p>
              </div>
            </div>
          </div>
        )}

        {isDoctorReview && (
          <div className="rounded-2xl border-2 border-amber-400 bg-amber-50 dark:bg-amber-950/70 dark:border-amber-700 p-5 shadow-sm">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-amber-500 text-white shadow-md">
                <AlertTriangle className="h-7 w-7" />
              </div>
              <div className="flex-1">
                <span className="inline-block text-[11px] font-bold uppercase tracking-wider text-amber-900 dark:text-amber-200 bg-amber-100 dark:bg-amber-900/60 px-2.5 py-0.5 rounded-full mb-1">
                  DOCTOR REVIEW REQUIRED
                </span>
                <h2 className="text-lg sm:text-xl font-extrabold text-amber-950 dark:text-amber-100">
                  DOCTOR MUST CHECK BEFORE GIVING MEDICINE
                </h2>
                <p className="mt-1 text-xs sm:text-sm text-amber-900/90 dark:text-amber-200 leading-relaxed font-medium">
                  Caution required. A senior doctor must review the warnings and click approve before administering this step.
                </p>
              </div>
            </div>
          </div>
        )}

        {isAllClear && (
          <div className="rounded-2xl border-2 border-teal-400 bg-teal-50 dark:bg-teal-950/70 dark:border-teal-700 p-5 shadow-sm">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-teal-600 text-white shadow-md">
                <CheckCircle2 className="h-7 w-7" />
              </div>
              <div className="flex-1">
                <span className="inline-block text-[11px] font-bold uppercase tracking-wider text-teal-800 dark:text-teal-200 bg-teal-100 dark:bg-teal-900/60 px-2.5 py-0.5 rounded-full mb-1">
                  ALL SAFETY CHECKS PASSED
                </span>
                <h2 className="text-lg sm:text-xl font-extrabold text-teal-950 dark:text-teal-100">
                  SAFE TO PROCEED WITH CARE STEPS
                </h2>
                <p className="mt-1 text-xs sm:text-sm text-teal-900/90 dark:text-teal-200 leading-relaxed font-medium">
                  No contraindications or harmful drug interactions were found. Follow the numbered emergency care steps below.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* PRIMARY SECTION: "WHAT TO DO" (Numbered Step-by-Step Care Process) */}
      <div className="mb-8">
        <div className="mb-4">
          <h2 className="text-xl sm:text-2xl font-black tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
            <span>What to do</span>
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Follow these emergency instructions step-by-step in numbered order:
          </p>
        </div>

        {/* CASE A: BLOCK (Dangerous Interaction Detected) */}
        {isBlock && (
          <div className="flex flex-col gap-3.5">
            {/* Step 1: WITHHOLD DANGEROUS DRUG */}
            <div className="rounded-2xl border-2 border-rose-300 dark:border-rose-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <div className="flex items-start gap-3.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-rose-600 text-white font-extrabold text-sm shadow">
                  1
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[11px] font-bold uppercase px-2 py-0.5 rounded-md bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-200 border border-rose-300 dark:border-rose-700">
                      DO NOT GIVE
                    </span>
                    <span className="text-xs font-semibold text-rose-700 dark:text-rose-300">
                      Absolute Danger
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                    STOP: Do NOT give Nitroglycerin / Nitrates
                  </h3>
                  <p className="mt-1 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    The patient has taken a PDE-5 inhibitor (such as Silagra / Sildenafil) in the past 24–48 hours. Giving Nitroglycerin together causes severe, life-threatening collapse in blood pressure.
                  </p>
                </div>
              </div>
            </div>

            {/* Step 2: INFORM DOCTOR */}
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <div className="flex items-start gap-3.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white font-extrabold text-sm shadow">
                  2
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[11px] font-bold uppercase px-2 py-0.5 rounded-md bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-200 border border-amber-300 dark:border-amber-700">
                      URGENT ACTION
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                    Inform Emergency Doctor Immediately
                  </h3>
                  <p className="mt-1 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    Tell the duty doctor that the patient reported recent Silagra/Sildenafil use. The doctor will choose alternative safe chest pain medications.
                  </p>
                </div>
              </div>
            </div>

            {/* Step 3: SAFE ALTERNATIVE ACTIONS */}
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <div className="flex items-start gap-3.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white font-extrabold text-sm shadow">
                  3
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[11px] font-bold uppercase px-2 py-0.5 rounded-md bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-200 border border-teal-300 dark:border-teal-700">
                      SAFE CARE STEPS
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                    Keep Patient Resting &amp; Perform 12-Lead ECG
                  </h3>
                  <p className="mt-1 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    Place patient in bed. Measure blood pressure and pulse. Perform 12-lead ECG within 10 minutes. Check oxygen level (SpO2).
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* CASE B: UNVERIFIED (Missing Data) */}
        {isUnverified && (
          <div className="flex flex-col gap-3.5">
            {/* Step 1: MEASURE MISSING VITALS */}
            <div className="rounded-2xl border-2 border-amber-300 dark:border-amber-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <div className="flex items-start gap-3.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white font-extrabold text-sm shadow">
                  1
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[11px] font-bold uppercase px-2 py-0.5 rounded-md bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-200 border border-amber-300 dark:border-amber-700">
                      REQUIRED ACTION
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                    Measure and Record Missing Vital Signs
                  </h3>
                  <p className="mt-1 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    Safety rules cannot run because some important details were not entered. Check the patient&apos;s Blood Pressure, Heart Rate, Breathing Rate, and Oxygen Level now.
                  </p>
                  {engine.checks_skipped && engine.checks_skipped.length > 0 && (
                    <div className="mt-2.5 p-3 rounded-xl bg-amber-100/60 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-xs text-amber-900 dark:text-amber-200 font-medium">
                      Missing items to check: {engine.checks_skipped.map((c) => c.reason || c.rule_id).slice(0, 3).join(', ')}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Step 2: ASK ABOUT CURRENT MEDICINES */}
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm">
              <div className="flex items-start gap-3.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white font-extrabold text-sm shadow">
                  2
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[11px] font-bold uppercase px-2 py-0.5 rounded-md bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-200 border border-teal-300 dark:border-teal-700">
                      CHECK MEDICINES
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                    Ask Patient or Attendant About Current Medicines
                  </h3>
                  <p className="mt-1 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    Confirm if the patient has taken any pills today, or has any known drug allergies (like Penicillin).
                  </p>
                </div>
              </div>
            </div>

            {/* Step 3: RETURN AND COMPLETE INTAKE */}
            <div className="rounded-2xl border-2 border-teal-300 dark:border-teal-700 bg-teal-50/50 dark:bg-teal-950/30 p-5 shadow-sm">
              <div className="flex items-start gap-3.5">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white font-extrabold text-sm shadow">
                  3
                </div>
                <div className="flex-1">
                  <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white mb-1">
                    Click to Update Patient Details
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 mb-3">
                    Return to the patient intake form and enter the measured numbers to receive safe step-by-step instructions.
                  </p>
                  <button
                    type="button"
                    onClick={() => navigate('/intake')}
                    className="flex items-center gap-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white px-5 py-2.5 text-xs font-bold transition-all shadow cursor-pointer"
                  >
                    <ArrowLeft className="h-4 w-4" />
                    <span>Enter Missing Numbers on Patient Details</span>
                  </button>
                </div>
              </div>
            </div>

            {/* If any steps were drafted in unverified state, show them badged as NOT APPROVED */}
            {triageResult.verified_steps && triageResult.verified_steps.length > 0 && (
              <div className="mt-2 flex flex-col gap-3">
                <span className="text-xs font-bold uppercase text-slate-500 dark:text-slate-400">
                  Care Guide Steps (Pending Verification — Do NOT Give Without Doctor Approval):
                </span>
                {triageResult.verified_steps.map((step, idx) => {
                  const draft = step.draft
                  const stepNum = draft.step_number || idx + 4
                  return (
                    <div
                      key={stepNum}
                      className="rounded-2xl border-2 border-amber-300 dark:border-amber-800 bg-amber-50/30 dark:bg-amber-950/20 p-5 shadow-sm"
                    >
                      <div className="flex items-start gap-3.5">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-500 text-white font-extrabold text-sm shadow">
                          {stepNum}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap mb-1.5">
                            <span className="text-[11px] font-bold uppercase px-2.5 py-0.5 rounded-md bg-amber-100 dark:bg-amber-950 text-amber-900 dark:text-amber-200 border border-amber-300 dark:border-amber-700">
                              NEEDS REVIEW (UNVERIFIED)
                            </span>
                            {draft.requested_dose && (
                              <span className="text-[11px] font-bold text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-800">
                                Dose: {draft.requested_dose.amount} {draft.requested_dose.unit}
                              </span>
                            )}
                          </div>
                          <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                            {draft.narrative_instruction}
                          </h3>
                          <p className="mt-1 text-xs text-amber-800 dark:text-amber-300 font-medium">
                            Cannot verify safety because patient vitals or history are missing. Doctor must confirm before giving.
                          </p>
                          {step.status === 'FLAGGED_HIGH' && (
                            <button
                              type="button"
                              onClick={() => handleOpenOverride(step.triggered_rule_ids?.[0] || 'HIGH_ALERT', stepNum)}
                              className="mt-3 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white px-3.5 py-1.5 rounded-lg transition-colors shadow shrink-0 cursor-pointer"
                            >
                              Doctor Review &amp; Approve
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* CASE C & D: CLEAR OR DOCTOR REVIEW WITH NUMBERED PROTOCOL STEPS */}
        {(isAllClear || isDoctorReview) && (
          <div className="flex flex-col gap-3.5">
            {triageResult.verified_steps && triageResult.verified_steps.length > 0 ? (
              triageResult.verified_steps.map((step, idx) => {
                const draft = step.draft
                const isBlockedStep = step.status === 'BLOCKED_STRUCK_THROUGH'
                const isHighStep = step.status === 'FLAGGED_HIGH'
                const stepNum = draft.step_number || idx + 1

                return (
                  <div
                    key={stepNum}
                    className={`rounded-2xl border-2 p-5 shadow-sm transition-all ${
                      isBlockedStep
                        ? 'border-rose-300 bg-rose-50/50 dark:bg-rose-950/20 dark:border-rose-800'
                        : isHighStep
                        ? 'border-amber-300 bg-amber-50/40 dark:bg-amber-950/20 dark:border-amber-700'
                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900'
                    }`}
                  >
                    <div className="flex items-start gap-3.5">
                      {/* Step Number Circle */}
                      <div
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white font-extrabold text-sm shadow ${
                          isBlockedStep
                            ? 'bg-rose-600'
                            : isHighStep
                            ? 'bg-amber-500'
                            : 'bg-teal-600'
                        }`}
                      >
                        {stepNum}
                      </div>

                      <div className="flex-1">
                        {/* Action Badge & Category */}
                        <div className="flex items-center gap-2 flex-wrap mb-1.5">
                          <span
                            className={`text-[11px] font-bold uppercase px-2.5 py-0.5 rounded-md ${
                              isBlockedStep
                                ? 'bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-200 border border-rose-300 dark:border-rose-700'
                                : isHighStep
                                ? 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-200 border border-amber-300 dark:border-amber-700'
                                : draft.action_type === 'administer'
                                ? 'bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-200 border border-teal-300 dark:border-teal-700'
                                : 'bg-sky-100 dark:bg-sky-950 text-sky-800 dark:text-sky-200 border border-sky-300 dark:border-sky-700'
                            }`}
                          >
                            {isBlockedStep
                              ? 'DO NOT GIVE'
                              : draft.action_type === 'administer'
                              ? 'GIVE MEDICINE'
                              : draft.action_type === 'diagnostic'
                              ? 'TEST / CHECK'
                              : draft.action_type === 'monitor'
                              ? 'MONITOR'
                              : draft.action_type.toUpperCase()}
                          </span>

                          {draft.route && (
                            <span className="text-[11px] text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                              Route: {draft.route}
                            </span>
                          )}

                          {draft.requested_dose && (
                            <span className="text-[11px] font-bold text-teal-700 dark:text-teal-400 bg-teal-50 dark:bg-teal-950/60 px-2 py-0.5 rounded border border-teal-200 dark:border-teal-800">
                              Dose: {draft.requested_dose.amount} {draft.requested_dose.unit}
                            </span>
                          )}
                        </div>

                        {/* Instruction */}
                        <h3
                          className={`text-base sm:text-lg font-bold leading-snug ${
                            isBlockedStep
                              ? 'text-rose-900 dark:text-rose-200 line-through decoration-rose-500 decoration-2'
                              : 'text-slate-900 dark:text-white'
                          }`}
                        >
                          {draft.narrative_instruction}
                        </h3>

                        {/* Block Rejection reason */}
                        {isBlockedStep && step.rejection_reasons && step.rejection_reasons.length > 0 && (
                          <div className="mt-2 text-xs font-semibold text-rose-700 dark:text-rose-300">
                            Reason: {step.rejection_reasons.join(', ')}
                          </div>
                        )}

                        {/* Warning if HIGH alert */}
                        {isHighStep && (
                          <div className="mt-3 p-3 rounded-xl bg-amber-100/70 dark:bg-amber-950/60 border border-amber-300 dark:border-amber-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div className="flex items-center gap-2 text-xs font-semibold text-amber-900 dark:text-amber-200">
                              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
                              <span>Caution: Doctor review required before giving this medicine.</span>
                            </div>
                            <button
                              type="button"
                              onClick={() => handleOpenOverride(step.triggered_rule_ids?.[0] || 'HIGH_ALERT', stepNum)}
                              className="text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white px-3 py-1.5 rounded-lg transition-colors shadow shrink-0 cursor-pointer"
                            >
                              Doctor Review &amp; Approve
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })
            ) : (
              <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm text-center">
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  No specific medicine orders are needed at this stage. Keep patient comfortable and re-check vitals.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Execution Pipeline & State Machine Trace (ADR 0017) */}
      {liveEvents.length > 0 && (
        <div className="pt-2">
          <div className="flex items-center justify-between mb-3 px-1">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-teal-500" />
              <h3 className="text-xs uppercase tracking-wider text-slate-500 dark:text-slate-400 font-bold">
                Software Execution Audit &amp; Event Trail
              </h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              {liveEvents.length} lifecycle events recorded
            </span>
          </div>
          <LiveProcessPanel events={liveEvents} isLoading={isLoading} />
        </div>
      )}

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