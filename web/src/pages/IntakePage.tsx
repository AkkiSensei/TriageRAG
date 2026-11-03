import React from 'react'
import { useNavigate } from 'react-router-dom'
import { PatientIntakeForm } from '@/features/intake/PatientIntakeForm'
import { LiveProcessPanel } from '@/features/execution/LiveProcessPanel'
import { useTriage } from '@/context/TriageContext'
import type { TriageApiRequest } from '@/lib/api'
import { DEMO_DISCLAIMER } from '@/lib/demoPatient'
import {
  Stethoscope,
  AlertCircle,
  ShieldAlert,
  Sparkles,
  AlertOctagon,
  RotateCcw,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react'

export const IntakePage: React.FC = () => {
  const navigate = useNavigate()
  const {
    patientRequest,
    triageResult,
    evaluatePatient,
    liveEvents,
    isLoading,
    error,
    isDemoActive,
    clearDemo,
  } = useTriage()

  const handleFormSubmit = async (req: TriageApiRequest) => {
    try {
      await evaluatePatient(req)
      // Live graph executes and completes on this page; user can review stages and click View Results
    } catch (err) {
      console.error('Triage submission error:', err)
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 space-y-6">
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
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-3xl leading-relaxed">
          Fill in the patient&apos;s age, vital signs, and current medicines. The system evaluates deterministic safety rules,
          verifies drug interactions via LangGraph, and renders clear machine-verified steps.
        </p>
      </div>

      {/* Synthetic Demo Patient Active Banner */}
      {isDemoActive && (
        <div
          data-testid="demo-patient-banner"
          className="rounded-3xl border-2 border-teal-500/40 dark:border-teal-400/40 bg-gradient-to-br from-teal-50/90 via-sky-50/50 to-white dark:from-slate-800 dark:via-teal-950/30 dark:to-slate-900 p-5 sm:p-6 shadow-soft space-y-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-teal-600 text-white shadow-soft-sm">
                <Sparkles className="h-4 w-4 text-amber-200" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                    Synthetic Demo Patient Pre-filled
                  </h2>
                  <span className="rounded-full bg-teal-100 dark:bg-teal-900/70 border border-teal-200 dark:border-teal-700 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-teal-800 dark:text-teal-200">
                    Synthetic Fixture
                  </span>
                  <span className="rounded-full bg-rose-100 dark:bg-rose-900/70 border border-rose-200 dark:border-rose-700 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-rose-800 dark:text-rose-200 flex items-center gap-1">
                    <AlertOctagon className="h-3 w-3" />
                    Expected Verdict: BLOCK
                  </span>
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">
                  58-year-old male with acute ischemic chest pain and recent Silagra (Sildenafil 50mg) dose (12h ago).
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={clearDemo}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-soft-sm transition-colors"
            >
              <RotateCcw className="h-3.5 w-3.5 text-slate-500" />
              <span>Clear Demo / Reset</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="rounded-2xl border border-slate-200/80 dark:border-slate-700/80 bg-white/80 dark:bg-slate-800/80 p-3.5 space-y-1.5">
              <div className="flex items-center gap-1.5 font-bold text-slate-900 dark:text-white">
                <AlertOctagon className="h-4 w-4 text-rose-600 dark:text-rose-400 shrink-0" />
                <span>Deterministic Contraindication Check (Rule R11)</span>
              </div>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                PDE5 inhibitor taken 12 hours ago (within 24h window). The deterministic safety engine strictly
                <strong className="text-rose-700 dark:text-rose-300"> BLOCKs </strong>
                Nitroglycerin to avoid fatal refractory hypotension. Under Rule R11, BLOCK alerts cannot be overridden.
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200/80 dark:border-slate-700/80 bg-white/80 dark:bg-slate-800/80 p-3.5 space-y-1.5">
              <div className="flex items-center gap-1.5 font-bold text-slate-900 dark:text-white">
                <CheckCircle2 className="h-4 w-4 text-teal-600 dark:text-teal-400 shrink-0" />
                <span>Code Decides; LLM Explains (Rule R1 &amp; R2)</span>
              </div>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
                Verdicts and checks come solely from deterministic code—not an LLM or this button. Missing glucose &amp;
                GCS remain strictly <span className="font-semibold text-slate-800 dark:text-slate-200">Unknown</span> (fail closed).
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/70 dark:bg-slate-900/60 px-3.5 py-2 text-[11px] text-slate-500 dark:text-slate-400">
            <span className="font-semibold text-slate-700 dark:text-slate-300">Disclaimer: </span>
            {DEMO_DISCLAIMER}
          </div>
        </div>
      )}

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

      {/* Responsive 2-Column Grid: Form + Live Execution Process Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Patient Intake Form (Left Column: 7 cols) */}
        <div className="lg:col-span-7 rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 sm:p-7 shadow-soft">
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

        {/* Live Process Graph & Activity Feed (Right Column: 5 cols / Stacked below on small screens) */}
        <div className="lg:col-span-5 space-y-4">
          {triageResult && !isLoading && (
            <div
              data-testid="evaluation-complete-banner"
              className="rounded-2xl border-2 border-emerald-500/60 dark:border-emerald-400/60 bg-emerald-50/90 dark:bg-emerald-950/60 p-4 shadow-soft flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-fade-in"
            >
              <div className="flex items-start gap-2.5">
                <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <div className="text-xs font-bold uppercase tracking-wider text-emerald-900 dark:text-emerald-200">
                    Run Complete · Verdict: {triageResult.engine.verdict}
                  </div>
                  <p className="text-[11px] text-emerald-800 dark:text-emerald-300 mt-0.5">
                    Deterministic pipeline finished. Click below to inspect the verified action plan.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => navigate('/report')}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold text-white bg-teal-600 hover:bg-teal-700 dark:bg-teal-500 dark:hover:bg-teal-600 shadow-sm transition-colors shrink-0 cursor-pointer w-full sm:w-auto justify-center"
              >
                <span>View Full Results</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <LiveProcessPanel events={liveEvents} isLoading={isLoading} onNavigateToReport={() => navigate('/report')} />
        </div>
      </div>
    </div>
  )
}

export default IntakePage
