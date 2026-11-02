import React, { useState } from 'react'
import {
  ShieldAlert,
  AlertTriangle,
  HelpCircle,
  CheckCircle2,
  ListChecks,
  Compass,
  ArrowRight,
  Clock,
  ChevronDown,
  ChevronUp,
  XCircle,
  Layers,
  Search,
} from 'lucide-react'
import type { TriageResponse, ConfidenceReport, DataQualityReport } from '@/lib/api'

interface ExplanationSectionProps {
  triage: TriageResponse
}

export const ExplanationSection: React.FC<ExplanationSectionProps> = ({ triage }) => {
  const [showTimeline, setShowTimeline] = useState(false)
  const [showNormalizationLedger, setShowNormalizationLedger] = useState(false)
  const [showRetrieverLedger, setShowRetrieverLedger] = useState(false)
  const [showDataQualityAudit, setShowDataQualityAudit] = useState(false)

  const engine = triage.engine
  const explanation = triage.explanation
  const verdict = engine.verdict
  const patient = triage.patient
  const inputPatient = (triage as { input_patient?: typeof patient }).input_patient || patient
  const executionTrace = (triage as { execution_trace?: Array<{ node: string; status: string; duration_ms: number; details?: Record<string, unknown> }> }).execution_trace || []
  const confidence: ConfidenceReport | undefined = (triage.confidence || triage.action_plan?.confidence) ?? undefined
  const dataQuality: DataQualityReport | undefined = (triage.data_quality || confidence?.data_quality) ?? undefined

  const getVerdictStyles = () => {
    switch (verdict) {
      case 'BLOCKED':
        return {
          bg: 'bg-rose-50 dark:bg-rose-950/40',
          border: 'border-rose-300 dark:border-rose-800',
          badgeBg: 'bg-rose-600 text-white',
          badgeText: 'BLOCKED',
          icon: <ShieldAlert className="h-6 w-6 text-rose-600 dark:text-rose-400" />,
          titleColor: 'text-rose-900 dark:text-rose-100',
        }
      case 'CHECKED_ALERTS':
        return {
          bg: 'bg-amber-50 dark:bg-amber-950/40',
          border: 'border-amber-300 dark:border-amber-800',
          badgeBg: 'bg-amber-600 text-white',
          badgeText: 'CHECKED WITH ALERTS',
          icon: <AlertTriangle className="h-6 w-6 text-amber-600 dark:text-amber-400" />,
          titleColor: 'text-amber-900 dark:text-amber-100',
        }
      case 'UNVERIFIED':
        return {
          bg: 'bg-purple-50 dark:bg-purple-950/40',
          border: 'border-purple-300 dark:border-purple-800',
          badgeBg: 'bg-purple-700 text-white',
          badgeText: 'UNVERIFIED',
          icon: <HelpCircle className="h-6 w-6 text-purple-600 dark:text-purple-400" />,
          titleColor: 'text-purple-900 dark:text-purple-100',
        }
      case 'CHECKED_CLEAR':
      default:
        return {
          bg: 'bg-teal-50 dark:bg-teal-950/40',
          border: 'border-teal-300 dark:border-teal-800',
          badgeBg: 'bg-teal-700 text-white',
          badgeText: 'CHECKED CLEAR',
          icon: <CheckCircle2 className="h-6 w-6 text-teal-600 dark:text-teal-400" />,
          titleColor: 'text-teal-900 dark:text-teal-100',
        }
    }
  }

  const vStyles = getVerdictStyles()
  const alertsCount = (engine.baseline_alerts?.length || 0) + (engine.plan_alerts?.length || 0)
  const skipsCount = engine.checks_skipped?.length || 0
  const stepsCount = triage.verified_steps?.length || 0
  const retrievalAbstained = Boolean(triage.retrieval?.abstained)

  // Timeline stage definitions for the 9-stage verification timeline
  const timelineStages = [
    { name: '1. Patient Input Validation', status: 'COMPLETED', note: 'All fields type-checked' },
    {
      name: '2. Clinical Data Normalization',
      status: (engine.unresolved_entities?.length || 0) > 0 ? 'UNRESOLVED ENTITIES' : 'COMPLETED',
      note: (engine.unresolved_entities?.length || 0) > 0
        ? `${engine.unresolved_entities?.length} unmapped entities`
        : 'Controlled units & vocabularies',
    },
    {
      name: '3. Physiological Risk Scoring',
      status: engine.score && engine.score.total_score !== null ? 'SCORED' : 'UNSCORED',
      note: engine.score ? `${engine.score.score_name} (Band: ${engine.score.band})` : 'Missing vitals',
    },
    {
      name: '4. Deterministic Safety Interlocks',
      status: alertsCount > 0
        ? (verdict === 'BLOCKED' ? 'BLOCK TRIGGERED' : 'ALERTS FLAGGED')
        : (skipsCount > 0 ? 'CHECKS SKIPPED' : (verdict === 'CHECKED_CLEAR' ? 'CHECKED CLEAR' : 'NO_ALERTS')),
      note: skipsCount > 0
        ? `${engine.checks_run} evaluated, ${skipsCount} skipped`
        : `${engine.checks_run} rules evaluated`,
    },
    {
      name: '5. Protocol Retrieval',
      status: retrievalAbstained ? 'ABSTAINED' : 'RETRIEVED',
      note: retrievalAbstained ? `${triage.retrieval?.abstain_code}` : `${triage.retrieval?.chunks?.length || 0} chunks (${triage.retrieval?.backend || 'bm25'})`,
    },
    {
      name: '6. Mock Plan Generation',
      status: triage.llm_fallback_mode ? 'SKIPPED (FALLBACK)' : 'DRAFTED',
      note: `Deterministic mock (${triage.provider_info?.requested_profile || 'COMPLIANT'})`,
    },
    {
      name: '7. Machine Verification',
      status: (() => {
        if (stepsCount === 0) return 'NO STEPS'
        const approvedCount = triage.verified_steps?.filter(s => s.status === 'APPROVED').length || 0
        if (approvedCount === stepsCount) return 'VERIFIED'
        if (approvedCount > 0) return 'PARTIALLY VERIFIED'
        return 'UNVERIFIED'
      })(),
      note: (() => {
        if (stepsCount === 0) return '0 steps evaluated'
        const approvedCount = triage.verified_steps?.filter(s => s.status === 'APPROVED').length || 0
        return `${approvedCount}/${stepsCount} steps approved`
      })(),
    },
    {
      name: '8. Safety Verdict Lattice',
      status: 'RESOLVED',
      note: `Final verdict: ${verdict}`,
    },
    {
      name: '9. Audit Hash Chain Sealed',
      status: triage.audit_hash ? 'SEALED' : 'UNAUDITED',
      note: triage.audit_hash ? `${triage.audit_hash.slice(0, 16)}...` : 'No log path configured',
    },
  ]

  return (
    <div className="flex flex-col gap-5">
      {/* 1. EXECUTIVE RESULT SUMMARY */}
      <div className={`rounded-2xl border ${vStyles.border} ${vStyles.bg} p-6 shadow-soft transition-all`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-black/5 dark:border-white/10 pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white dark:bg-slate-800 shadow-sm">
              {vStyles.icon}
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold tracking-wider ${vStyles.badgeBg} shadow-sm`}>
                  {vStyles.badgeText}
                </span>
                {confidence && (
                  <span
                    className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold tracking-wider shadow-sm ${
                      confidence.level === 'HIGH'
                        ? 'bg-emerald-600 text-white'
                        : confidence.level === 'MEDIUM'
                          ? 'bg-amber-600 text-white'
                          : 'bg-rose-600 text-white'
                    }`}
                  >
                    {confidence.level} CONFIDENCE
                  </span>
                )}
                {dataQuality && (
                  <span className="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-white/80 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300">
                    Intake Completeness: {dataQuality.measured_count}/12 Measured &bull; {dataQuality.assumed_count} Assumed &bull; {dataQuality.missing_count} Missing ({Number(dataQuality.completeness_pct).toFixed(0)}%)
                  </span>
                )}
              </div>
              <h2 className={`text-base sm:text-lg font-bold ${vStyles.titleColor}`}>
                {explanation?.headline || `Result: ${verdict}`}
              </h2>
            </div>
          </div>

          {/* Quick counts summary */}
          <div className="flex items-center gap-2 flex-wrap font-mono text-[11px]">
            <span className="bg-white/80 dark:bg-black/30 border border-slate-200/80 dark:border-slate-800 px-2.5 py-1 rounded-xl">
              <span className="font-bold text-slate-900 dark:text-white">{engine.checks_run}</span> Checks Evaluated
            </span>
            <span className="bg-white/80 dark:bg-black/30 border border-slate-200/80 dark:border-slate-800 px-2.5 py-1 rounded-xl">
              <span className="font-bold text-slate-900 dark:text-white">{alertsCount}</span> Alerts
            </span>
            <span className="bg-white/80 dark:bg-black/30 border border-slate-200/80 dark:border-slate-800 px-2.5 py-1 rounded-xl">
              <span className="font-bold text-slate-900 dark:text-white">{skipsCount}</span> Unresolved
            </span>
          </div>
        </div>

        {/* Plain Language Explanation */}
        <p className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed font-sans mb-4">
          {explanation?.plain_language_summary ||
            'The clinical engine evaluated deterministic safety interlocks and protocol evidence against patient parameters.'}
        </p>

        {/* Generation & Retrieval Transparency Pill */}
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-black/5 dark:border-white/10 text-[11px] font-mono text-slate-600 dark:text-slate-400">
          <span className="font-semibold">Generation Mode:</span>
          <span className="px-2 py-0.5 rounded bg-white dark:bg-black/40 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 font-bold">
            {triage.provider_info?.generation_mode === 'deterministic_mock' ? 'Deterministic Mock (Offline)' : 'Mock Generation'}
          </span>
          <span className="text-slate-400">&bull;</span>
          <span className="font-semibold">Retrieval:</span>
          <span className="px-2 py-0.5 rounded bg-white dark:bg-black/40 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 font-bold uppercase">
            {triage.retrieval?.backend || 'BM25'}
          </span>
          {retrievalAbstained && (
            <span className="px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-900 dark:text-amber-200 font-bold">
              Abstained: {triage.retrieval?.abstain_code}
            </span>
          )}
        </div>
        {explanation?.generation_disclosure && (
          <p className="mt-2 text-[11px] font-mono text-slate-500 dark:text-slate-400 leading-relaxed">
            {explanation.generation_disclosure}
          </p>
        )}
      </div>

      {/* 1.5. CLINICAL ACTION PLAN & ATTENDANT WORKFLOW */}
      {triage.action_plan && (
        <div className="rounded-2xl border border-indigo-200 dark:border-indigo-800/60 bg-gradient-to-br from-indigo-50/70 via-white to-purple-50/50 dark:from-slate-900 dark:via-slate-850 dark:to-indigo-950/30 p-6 shadow-soft">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-indigo-100 dark:border-indigo-900/50 pb-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm">
                <ListChecks className="h-5 w-5" />
              </div>
              <div>
                <span className="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider bg-indigo-100 text-indigo-800 dark:bg-indigo-900/80 dark:text-indigo-200 mb-1">
                  Deterministic Attendant Workflow
                </span>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Step-by-Step Clinical Action Plan
                </h3>
              </div>
            </div>
            <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
              Derived from Rule Engine &bull; Zero LLM Hallucination
            </span>
          </div>

          {/* Decision Summary */}
          {Boolean(triage.action_plan.decision_summary) && (
            <div className="mb-4 rounded-xl bg-white/90 dark:bg-slate-800/90 p-4 border border-indigo-100 dark:border-indigo-900/40 text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed font-sans shadow-xs">
              <span className="font-bold text-indigo-900 dark:text-indigo-300 block mb-1 uppercase text-[11px] tracking-wider font-mono">
                Clinical Decision Summary
              </span>
              {triage.action_plan.decision_summary}
            </div>
          )}

          {/* Clinical Rationale & Why Decision */}
          {Boolean(triage.action_plan.why_decision) && (
            <div className="mb-4 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/30 p-4 border border-indigo-200/70 dark:border-indigo-800/50 text-xs sm:text-sm text-indigo-950 dark:text-indigo-200 leading-relaxed font-sans shadow-xs">
              <span className="font-bold text-indigo-900 dark:text-indigo-300 block mb-1 uppercase text-[11px] tracking-wider font-mono">
                Clinical Safety Rationale
              </span>
              {triage.action_plan.why_decision}
            </div>
          )}

          {/* Confidence Trust Drivers */}
          {Boolean(confidence?.reasons?.length) && (
            <div className="mb-4 rounded-xl bg-slate-50 dark:bg-slate-800/80 p-3.5 border border-slate-200 dark:border-slate-700">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2 pb-2 border-b border-slate-200/60 dark:border-slate-700/60">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px] font-bold font-mono uppercase tracking-wider text-slate-800 dark:text-slate-200">
                    Evidence & Verification Status ({confidence?.level})
                  </span>
                  {confidence?.rule_evidence && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300">
                      Rule: {confidence.rule_evidence}
                    </span>
                  )}
                  {confidence?.case_completeness && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-200">
                      Case: {confidence.case_completeness}
                    </span>
                  )}
                </div>
                <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400">
                  Heuristic Index: {confidence?.score} (Not a clinical probability)
                </span>
              </div>
              <ul className="space-y-1 text-xs text-slate-700 dark:text-slate-300 font-sans">
                {confidence?.reasons?.map((r, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-indigo-600 dark:text-indigo-400 font-bold font-mono">&bull;</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Protocol Match Summary */}
          {Boolean(triage.action_plan.protocol_match_summary) && (
            <div className="mb-4 flex items-center gap-2 p-3 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-xs text-teal-900 dark:text-teal-200 font-sans">
              <CheckCircle2 className="h-4 w-4 text-teal-600 dark:text-teal-400 shrink-0" />
              <span>{triage.action_plan.protocol_match_summary}</span>
            </div>
          )}

          {/* Input Data Quality Audit */}
          {dataQuality && (
            <div className="mb-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/90 p-4 shadow-xs">
              <div
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setShowDataQualityAudit(!showDataQualityAudit)}
              >
                <div className="flex items-center gap-2">
                  <ListChecks className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                  <span className="text-xs font-bold uppercase tracking-wider font-mono text-slate-900 dark:text-white">
                    Data Quality Audit &bull; {dataQuality.measured_count}/12 Measured &bull; {dataQuality.assumed_count} Assumed &bull; {dataQuality.missing_count} Missing ({Number(dataQuality.completeness_pct).toFixed(0)}% Complete)
                  </span>
                </div>
                <button
                  type="button"
                  className="text-xs text-indigo-600 dark:text-indigo-400 font-mono flex items-center gap-1 hover:underline"
                >
                  {showDataQualityAudit ? 'Hide Audit' : 'Show Breakdown'}
                  {showDataQualityAudit ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>
              </div>

              {showDataQualityAudit && (
                <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-700 text-xs">
                  <p className="text-[11px] font-mono text-slate-500 dark:text-slate-400 mb-2">
                    Scope: 12 standard triage parameters (HR, SBP, DBP, RR, SpO2, Temp, Consciousness/GCS, Weight, Allergies, Meds, Age, Sex). Assumed demo defaults do not count toward measured completeness.
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="rounded-lg bg-emerald-50/60 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/50 p-2.5">
                      <span className="font-bold text-emerald-800 dark:text-emerald-300 font-mono text-[11px] block mb-1">
                        MEASURED CLINICALLY ({dataQuality.measured_count})
                      </span>
                      <ul className="space-y-1 font-mono text-[11px] text-emerald-900 dark:text-emerald-200">
                        {dataQuality.measured_fields?.map((f, i) => <li key={i}>&bull; {f}</li>)}
                      </ul>
                    </div>
                    <div className="rounded-lg bg-amber-50/60 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50 p-2.5">
                      <span className="font-bold text-amber-800 dark:text-amber-300 font-mono text-[11px] block mb-1">
                        ASSUMED DEMO DEFAULTS ({dataQuality.assumed_count})
                      </span>
                      <ul className="space-y-1 font-mono text-[11px] text-amber-900 dark:text-amber-200">
                        {dataQuality.assumed_fields && dataQuality.assumed_fields.length > 0 ? (
                          dataQuality.assumed_fields.map((f, i) => <li key={i}>&bull; {f}</li>)
                        ) : (
                          <li className="italic text-slate-400">None</li>
                        )}
                      </ul>
                    </div>
                    <div className="rounded-lg bg-rose-50/60 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800/50 p-2.5">
                      <span className="font-bold text-rose-800 dark:text-rose-300 font-mono text-[11px] block mb-1">
                        MISSING / UNKNOWN ({dataQuality.missing_count})
                      </span>
                      <ul className="space-y-1 font-mono text-[11px] text-rose-900 dark:text-rose-200">
                        {dataQuality.missing_fields && dataQuality.missing_fields.length > 0 ? (
                          dataQuality.missing_fields.map((f, i) => <li key={i}>&bull; {f}</li>)
                        ) : (
                          <li className="italic text-slate-400">None</li>
                        )}
                      </ul>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Assumptions Pills */}
          {Boolean(triage.action_plan.assumptions?.length) && (
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-mono font-bold text-amber-800 dark:text-amber-300">
                Assumed Demo Defaults:
              </span>
              {triage.action_plan.assumptions?.map((assump, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg text-[11px] font-mono bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800/70 text-amber-900 dark:text-amber-200"
                >
                  {assump}
                </span>
              ))}
            </div>
          )}

          {/* Immediate Actions */}
          {Boolean(triage.action_plan.immediate_actions?.length) && (
            <div className="mb-4">
              <h4 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-2">
                Immediate Actions
              </h4>
              <div className="flex flex-col gap-2">
                {triage.action_plan.immediate_actions?.map((act, idx) => {
                  const uColor = act.urgency === 'immediate'
                    ? 'border-rose-300 bg-rose-50/80 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200'
                    : (act.urgency === 'urgent'
                      ? 'border-amber-300 bg-amber-50/80 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200'
                      : 'border-emerald-300 bg-emerald-50/80 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200')
                  return (
                    <div
                      key={idx}
                      className={`flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-xl border text-xs ${uColor}`}
                    >
                      <div className="flex items-start gap-2.5">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase shrink-0 mt-0.5 bg-black/10 dark:bg-white/10">
                          {act.urgency}
                        </span>
                        <div>
                          <span className="font-bold block text-xs sm:text-sm">{act.title}</span>
                          <span className="opacity-90">{act.description}</span>
                        </div>
                      </div>
                      <span className="text-[11px] font-mono opacity-80 shrink-0 italic sm:text-right">
                        {act.reason}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Medications Instructions */}
          {Boolean(triage.action_plan.medications?.length) && (
            <div className="mb-4">
              <h4 className="text-xs font-bold font-mono uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-2">
                Medication Administration Instructions
              </h4>
              <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
                <table className="w-full text-left text-xs font-sans">
                  <thead className="bg-slate-50 dark:bg-slate-900/60 font-mono text-[11px] text-slate-600 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
                    <tr>
                      <th className="px-3.5 py-2.5">Medication</th>
                      <th className="px-3.5 py-2.5">Dose</th>
                      <th className="px-3.5 py-2.5">Route</th>
                      <th className="px-3.5 py-2.5">Timing</th>
                      <th className="px-3.5 py-2.5">Indication</th>
                      <th className="px-3.5 py-2.5">Why Chosen / Derivation</th>
                      <th className="px-3.5 py-2.5">Excluded Alternatives</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60 font-mono">
                    {triage.action_plan.medications?.map((m, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-700/20">
                        <td className="px-3.5 py-2.5 font-bold text-teal-700 dark:text-teal-400">
                          {m.medication_name}
                        </td>
                        <td className="px-3.5 py-2.5 font-bold">{m.dose}</td>
                        <td className="px-3.5 py-2.5 uppercase">{m.route}</td>
                        <td className="px-3.5 py-2.5">{m.timing}</td>
                        <td className="px-3.5 py-2.5 font-sans text-slate-600 dark:text-slate-300 text-[11px]">
                          {m.indication}
                        </td>
                        <td className="px-3.5 py-2.5 font-sans text-slate-600 dark:text-slate-300 text-[11px]">
                          <div>{m.why_chosen || 'Standard protocol first-line agent'}</div>
                          {m.dose_computation_source && (
                            <div className="text-[10px] text-indigo-600 dark:text-indigo-400 font-mono mt-0.5">
                              Source: {m.dose_computation_source}
                            </div>
                          )}
                        </td>
                        <td className="px-3.5 py-2.5 font-sans text-slate-500 dark:text-slate-400 text-[11px]">
                          {m.why_not_alternatives && m.why_not_alternatives.length > 0 ? (
                            <ul className="list-disc pl-3 space-y-0.5">
                              {m.why_not_alternatives.map((alt, aidx) => (
                                <li key={aidx}>{alt}</li>
                              ))}
                            </ul>
                          ) : (
                            <span className="italic text-slate-400">None</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Non-Approved / Prohibited Proposed Steps */}
          {Boolean(triage.action_plan.unapproved_draft_steps?.length) && (
            <div className="mb-4 rounded-xl border border-rose-300 dark:border-rose-900 bg-rose-50/70 dark:bg-rose-950/30 p-4">
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="h-4 w-4 text-rose-600 dark:text-rose-400 shrink-0" />
                <h4 className="text-xs font-bold font-mono uppercase tracking-wider text-rose-900 dark:text-rose-200">
                  Non-Approved / Prohibited Proposed Steps (Administration Prohibited)
                </h4>
              </div>
              <p className="text-[11px] text-rose-800 dark:text-rose-300 mb-2 font-sans">
                The following proposed steps were evaluated by machine verification and are NOT approved for clinical administration:
              </p>
              <div className="flex flex-col gap-1.5 font-mono text-xs">
                {triage.action_plan.unapproved_draft_steps?.map((u, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-lg bg-white/90 dark:bg-slate-900/90 border border-rose-200 dark:border-rose-900/60 text-rose-900 dark:text-rose-200"
                  >
                    &bull; {u}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Monitoring & Escalation Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Monitoring */}
            {Boolean(triage.action_plan.monitoring_steps?.length) && (
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-800/70 p-3.5">
                <h4 className="text-[11px] font-bold font-mono uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-2">
                  Scheduled Monitoring
                </h4>
                <div className="flex flex-col gap-2">
                  {triage.action_plan.monitoring_steps?.map((mon, idx) => (
                    <div key={idx} className="text-xs">
                      <span className="font-bold text-slate-900 dark:text-white block font-sans">
                        {mon.monitor}
                      </span>
                      <div className="flex items-center gap-2 text-[11px] font-mono text-slate-600 dark:text-slate-400 mt-0.5">
                        <span className="font-bold text-indigo-700 dark:text-indigo-400">{mon.frequency}</span>
                        <span>&bull;</span>
                        <span>Trigger: {mon.trigger}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Escalation */}
            {Boolean(triage.action_plan.escalation_steps?.length) && (
              <div className="rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50/40 dark:bg-rose-950/20 p-3.5">
                <h4 className="text-[11px] font-bold font-mono uppercase tracking-wider text-rose-800 dark:text-rose-400 mb-2">
                  Escalation Triggers
                </h4>
                <div className="flex flex-col gap-2">
                  {triage.action_plan.escalation_steps?.map((esc, idx) => (
                    <div key={idx} className="text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-rose-950 dark:text-rose-200 font-sans">
                          {esc.when}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-200 dark:bg-rose-900/60 text-rose-900 dark:text-rose-200">
                          {esc.escalate_to}
                        </span>
                      </div>
                      <span className="text-[11px] text-rose-800/80 dark:text-rose-300/80 font-sans block mt-0.5">
                        {esc.reason}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 2. "WHY DID I GET THIS RESULT?" & REJECTED ALTERNATIVES */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 flex flex-col gap-4">
          {/* Why Did I Get This Result Card */}
          <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 shadow-soft">
            <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-700 pb-3 mb-3">
              <Compass className="h-4 w-4 text-teal-700 dark:text-teal-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                Why Did I Get This Result?
              </h3>
            </div>

            <div className="flex flex-col gap-2.5">
              {explanation?.outcome_reasons && explanation.outcome_reasons.length > 0 ? (
                explanation.outcome_reasons.map((reason, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2.5 rounded-xl bg-slate-50 dark:bg-slate-900 p-3 text-xs text-slate-800 dark:text-slate-200 border border-slate-200/80 dark:border-slate-700"
                  >
                    <ArrowRight className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400 shrink-0 mt-0.5" />
                    <span className="leading-relaxed font-sans">{reason}</span>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400 italic">
                  No specific blocking interlocks or contraindication alerts triggered.
                </p>
              )}
            </div>
          </div>

          {/* Why Other Paths Were Rejected Card */}
          {Boolean(((explanation as { rejected_paths?: string[] })?.rejected_paths?.length || triage.action_plan?.rejected_alternatives?.length)) && (
            <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 shadow-soft">
              <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-700 pb-3 mb-3">
                <XCircle className="h-4 w-4 text-rose-600 dark:text-rose-400" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                  Why Alternative Paths Were Rejected
                </h3>
              </div>

              <div className="flex flex-col gap-2">
                {[
                  ...((explanation as { rejected_paths?: string[] }).rejected_paths || []),
                  ...(triage.action_plan?.rejected_alternatives || []),
                ].map((rej, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 rounded-xl bg-rose-50/50 dark:bg-rose-950/20 p-2.5 text-xs text-slate-700 dark:text-slate-300 border border-rose-100 dark:border-rose-900/40"
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-rose-500 shrink-0 mt-1.5" />
                    <span className="leading-relaxed font-sans">{rej}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Permitted Clinical Actions Card */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 shadow-soft">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-700 pb-3 mb-3">
            <ListChecks className="h-4 w-4 text-teal-700 dark:text-teal-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white">
              Permitted Next Steps
            </h3>
          </div>

          <ul className="flex flex-col gap-2 text-xs text-slate-700 dark:text-slate-300">
            {explanation?.permitted_ui_actions && explanation.permitted_ui_actions.length > 0 ? (
              explanation.permitted_ui_actions.map((act, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-500 shrink-0 mt-1.5" />
                  <span className="leading-relaxed">{act}</span>
                </li>
              ))
            ) : (
              <li className="italic text-slate-400">Review clinical presentation with attending physician.</li>
            )}
          </ul>
        </div>
      </div>

      {/* 3. INPUT NORMALIZATION LEDGER (INPUT VS NORMALIZED PATIENT) */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 shadow-soft">
        <button
          type="button"
          onClick={() => setShowNormalizationLedger(!showNormalizationLedger)}
          className="flex w-full items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 hover:text-teal-700 dark:hover:text-teal-300 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-teal-600 dark:text-teal-400" />
            <span>Input Normalization Ledger (Input vs Normalized Entities)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono font-normal text-slate-500 dark:text-slate-400">
              {((patient?.medications?.length || 0) + (patient?.allergies?.length || 0))} entities mapped
            </span>
            {showNormalizationLedger ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>
        </button>

        {showNormalizationLedger && (
          <div className="mt-4 flex flex-col gap-4 pt-3 border-t border-slate-100 dark:border-slate-700">
            {/* Medications Mapping */}
            <div>
              <h4 className="text-[11px] font-mono font-bold uppercase text-slate-700 dark:text-slate-300 mb-2">
                Medications Normalization
              </h4>
              {patient?.medications && patient.medications.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-700 text-[10px] font-mono text-slate-500 uppercase">
                        <th className="py-2 pr-3">Input Text</th>
                        <th className="py-2 px-3">Resolved Active Ingredients</th>
                        <th className="py-2 pl-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-[11px] font-mono">
                      {patient.medications.map((m, idx) => {
                        const inputRaw = (inputPatient?.medications?.[idx]?.raw_text) || m.raw_text
                        const ings = m.ingredients?.map(i => i.ingredient_id).join(', ') || 'None'
                        return (
                          <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/50">
                            <td className="py-2 pr-3 font-semibold text-slate-900 dark:text-slate-100">{inputRaw}</td>
                            <td className="py-2 px-3 text-slate-700 dark:text-slate-300">{ings}</td>
                            <td className="py-2 pl-3">
                              {m.resolved ? (
                                <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300">
                                  RESOLVED
                                </span>
                              ) : (
                                <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 dark:bg-amber-950 text-amber-900 dark:text-amber-200">
                                  UNRESOLVED {m.suggestion ? `(Suggest: ${m.suggestion})` : ''}
                                </span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400 italic">No medications recorded.</p>
              )}
            </div>

            {/* Allergies Mapping */}
            <div>
              <h4 className="text-[11px] font-mono font-bold uppercase text-slate-700 dark:text-slate-300 mb-2">
                Allergies Normalization
              </h4>
              {patient?.allergies && patient.allergies.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-700 text-[10px] font-mono text-slate-500 uppercase">
                        <th className="py-2 pr-3">Input Substance</th>
                        <th className="py-2 px-3">Normalized Allergen ID</th>
                        <th className="py-2 pl-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-[11px] font-mono">
                      {patient.allergies.map((a, idx) => {
                        const inputRaw = (inputPatient?.allergies?.[idx]?.raw_substance) || a.raw_substance
                        return (
                          <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/50">
                            <td className="py-2 pr-3 font-semibold text-slate-900 dark:text-slate-100">{inputRaw}</td>
                            <td className="py-2 px-3 text-slate-700 dark:text-slate-300">{a.normalized_allergen_id || 'None'}</td>
                            <td className="py-2 pl-3">
                              {a.resolved ? (
                                <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300">
                                  RESOLVED
                                </span>
                              ) : (
                                <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 dark:bg-amber-950 text-amber-900 dark:text-amber-200">
                                  UNRESOLVED {a.suggestion ? `(Suggest: ${a.suggestion})` : ''}
                                </span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-slate-500 dark:text-slate-400 italic">No allergies recorded.</p>
              )}
            </div>

            {/* Demographics & Measurements */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-100 dark:border-slate-700 text-[11px] font-mono">
              <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-900">
                <span className="text-slate-500 block text-[10px]">Population</span>
                <span className="font-bold text-slate-800 dark:text-slate-200 uppercase">{String((patient?.age as { population_category?: string } | undefined)?.population_category || 'adult')}</span>
              </div>
              <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-900">
                <span className="text-slate-500 block text-[10px]">Weight</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">
                  {patient?.weight_kg?.value ? `${patient.weight_kg.value} kg (${patient.weight_kg.source})` : 'Unknown'}
                </span>
              </div>
              <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-900">
                <span className="text-slate-500 block text-[10px]">Medication History</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">{patient?.medication_history_status || 'unknown'}</span>
              </div>
              <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-900">
                <span className="text-slate-500 block text-[10px]">Allergy History</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">{patient?.allergy_history_status || 'unknown'}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 4. RETRIEVER EVIDENCE & PLAN GROUNDING LEDGER */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 shadow-soft">
        <button
          type="button"
          onClick={() => setShowRetrieverLedger(!showRetrieverLedger)}
          className="flex w-full items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 hover:text-teal-700 dark:hover:text-teal-300 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-teal-600 dark:text-teal-400" />
            <span>Retriever Evidence &amp; Plan Grounding Ledger</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono font-normal text-slate-500 dark:text-slate-400">
              {triage.retrieval?.chunks?.length || 0} chunks &bull; {triage.verified_steps?.length || 0} plan steps
            </span>
            {showRetrieverLedger ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>
        </button>

        {showRetrieverLedger && (
          <div className="mt-4 flex flex-col gap-4 pt-3 border-t border-slate-100 dark:border-slate-700">
            {/* Retrieval Parameters */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-[11px] font-mono">
              <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-900">
                <span className="text-slate-500 block text-[10px]">Retriever Query</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">{triage.retrieval?.query || '(automatic syndrome query)'}</span>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-900">
                <span className="text-slate-500 block text-[10px]">Backend &amp; Filters</span>
                <span className="font-bold text-slate-800 dark:text-slate-200 uppercase">
                  {triage.retrieval?.backend || 'BM25'} (pop: {triage.retrieval?.filters?.population || 'all'})
                </span>
              </div>
              <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-900">
                <span className="text-slate-500 block text-[10px]">Abstention Status</span>
                <span className={`font-bold ${retrievalAbstained ? 'text-amber-700 dark:text-amber-300' : 'text-teal-700 dark:text-teal-300'}`}>
                  {retrievalAbstained ? `Abstained (${triage.retrieval?.abstain_code})` : 'Active / Evaluated'}
                </span>
              </div>
            </div>

            {/* Chunks Considered Table */}
            {triage.retrieval?.chunks && triage.retrieval.chunks.length > 0 && (
              <div>
                <h4 className="text-[11px] font-mono font-bold uppercase text-slate-700 dark:text-slate-300 mb-2">
                  Retrieved Protocol Evidence Chunks
                </h4>
                <div className="flex flex-col gap-2">
                  {triage.retrieval.chunks.map((chk, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-slate-200/80 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-900 p-3 text-xs font-mono"
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-bold text-slate-900 dark:text-white text-[11px]">
                          Rank #{idx + 1}: {chk.chunk_id ? `[${chk.chunk_id}] ` : ''}{chk.doc_id} &bull; {chk.section}
                        </span>
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300">
                          Score: {typeof chk.score === 'number' ? (chk.score as number).toFixed(2) : String(chk.score ?? '')}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-400 font-sans leading-relaxed line-clamp-2">
                        {chk.text}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Plan Grounding Citations */}
            {triage.verified_steps && triage.verified_steps.length > 0 && (
              <div>
                <h4 className="text-[11px] font-mono font-bold uppercase text-slate-700 dark:text-slate-300 mb-2">
                  Plan Steps Grounding &amp; Citation Verification
                </h4>
                <div className="flex flex-col gap-2">
                  {triage.verified_steps.map((step, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-slate-200/80 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-900 p-3 text-xs font-mono"
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-bold text-slate-900 dark:text-white text-[11px]">
                          Step #{step.draft?.step_number}: {step.draft?.action_type} {step.draft?.drug_id || ''}
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${step.citation_verified ? 'bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300' : 'bg-amber-100 dark:bg-amber-950 text-amber-900 dark:text-amber-200'}`}>
                          {step.citation_verified ? 'CITATION VERIFIED' : 'CITATION UNVERIFIED'}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-400 font-sans leading-relaxed mb-1">
                        {step.draft?.narrative_instruction}
                      </p>
                      <div className="text-[10px] text-slate-500 dark:text-slate-400">
                        <span>Citations: {step.draft?.citations?.map(c => c.chunk_id).join(', ') || 'None'}</span>
                        <span className="mx-2">&bull;</span>
                        <span>Overlap: {String(step.citation_overlap_score || 0)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 5. COMPLETED VS UNRESOLVED CHECKS SCOPE */}
      {(Boolean(explanation?.completed_checks?.length) || Boolean(explanation?.unresolved_checks?.length)) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 shadow-soft">
            <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-700 pb-3 mb-3">
              <CheckCircle2 className="h-4 w-4 text-teal-600 dark:text-teal-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                Completed Checks ({explanation?.completed_checks?.length || 0})
              </h3>
            </div>
            <ul className="flex flex-col gap-2 text-xs text-slate-700 dark:text-slate-300">
              {explanation?.completed_checks?.map((chk, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-teal-500 shrink-0 mt-1.5" />
                  <span className="leading-relaxed">{chk}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-5 shadow-soft">
            <div className="flex items-center gap-2 border-b border-slate-100 dark:border-slate-700 pb-3 mb-3">
              <HelpCircle className="h-4 w-4 text-violet-600 dark:text-violet-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                Unresolved Checks &amp; Scope ({explanation?.unresolved_checks?.length || 0})
              </h3>
            </div>
            <ul className="flex flex-col gap-2 text-xs text-slate-700 dark:text-slate-300">
              {explanation?.unresolved_checks?.map((chk, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-500 shrink-0 mt-1.5" />
                  <span className="leading-relaxed">{chk}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* 6. EXECUTION PIPELINE TIMELINE & 8-STAGE LANGGRAPH DECISION LEDGER */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 shadow-soft">
        <button
          type="button"
          onClick={() => setShowTimeline(!showTimeline)}
          className="flex w-full items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 hover:text-teal-700 dark:hover:text-teal-300 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-teal-600 dark:text-teal-400" />
            <span>Execution Pipeline Timeline (9 Verification Stages)</span>
          </div>
          <div className="flex items-center gap-2">
            {executionTrace.length > 0 && (
              <span className="text-[11px] font-mono font-normal text-slate-500 dark:text-slate-400">
                {executionTrace.length} LangGraph nodes traced
              </span>
            )}
            {showTimeline ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>
        </button>

        {showTimeline && (
          <div className="mt-4 flex flex-col gap-4 pt-3 border-t border-slate-100 dark:border-slate-700">
            {/* Live LangGraph Execution Trace Ledger */}
            {executionTrace.length > 0 && (
              <div className="mb-2">
                <h4 className="text-[11px] font-mono font-bold uppercase text-slate-700 dark:text-slate-300 mb-2">
                  Live LangGraph Runtime State Nodes ({executionTrace.length} Nodes)
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 font-mono text-xs">
                  {executionTrace.map((tr, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700 bg-slate-50 dark:bg-slate-900"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-[11px] text-slate-900 dark:text-slate-100 truncate">
                          {idx + 1}. {tr.node}
                        </span>
                        <span className="text-[10px] font-bold px-1 py-0.5 rounded bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300">
                          {tr.duration_ms} ms
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-500 dark:text-slate-400 truncate">
                        Status: {tr.status}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Standard 9 Verification Stages Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
              {timelineStages.map((stage, idx) => (
                <div
                  key={idx}
                  className="rounded-xl border border-slate-200/80 dark:border-slate-700 bg-slate-50/60 dark:bg-slate-900 p-2.5 text-xs font-mono"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-slate-700 dark:text-slate-300 text-[11px] truncate">
                      {stage.name}
                    </span>
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300">
                      {stage.status}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 dark:text-slate-400 truncate">{stage.note}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default ExplanationSection
