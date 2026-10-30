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
} from 'lucide-react'
import type { TriageResponse } from '@/lib/api'

interface ExplanationSectionProps {
  triage: TriageResponse
}

export const ExplanationSection: React.FC<ExplanationSectionProps> = ({ triage }) => {
  const [showTimeline, setShowTimeline] = useState(false)
  const engine = triage.engine
  const explanation = triage.explanation
  const verdict = engine.verdict

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

  // Timeline stage definitions
  const timelineStages = [
    { name: '1. Patient Input Validation', status: 'COMPLETED', note: 'All fields type-checked' },
    { name: '2. Clinical Data Normalization', status: 'COMPLETED', note: 'Controlled units & vocabularies' },
    {
      name: '3. Physiological Risk Scoring',
      status: engine.score && engine.score.total_score !== null ? 'SCORED' : 'UNSCORED',
      note: engine.score ? `${engine.score.score_name} (Band: ${engine.score.band})` : 'Missing vitals',
    },
    {
      name: '4. Deterministic Safety Interlocks',
      status: alertsCount > 0 ? (verdict === 'BLOCKED' ? 'BLOCK TRIGGERED' : 'ALERTS FLAGGED') : 'CLEAR',
      note: `${engine.checks_run} rules evaluated`,
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
      status: stepsCount > 0 ? 'VERIFIED' : 'NO STEPS',
      note: `${stepsCount} steps evaluated`,
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
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white dark:bg-[#132226] shadow-sm">
              {vStyles.icon}
            </div>
            <div>
              <span className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold tracking-wider ${vStyles.badgeBg} shadow-sm mb-1`}>
                {vStyles.badgeText}
              </span>
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
      </div>

      {/* 2. "WHY DID I GET THIS RESULT?" & NEXT ACTIONS */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 shadow-soft">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-[#1e3840] pb-3 mb-3">
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
                  className="flex items-start gap-2.5 rounded-xl bg-slate-50 dark:bg-[#0c1618] p-3 text-xs text-slate-800 dark:text-slate-200 border border-slate-200/80 dark:border-[#1e3840]"
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

        {/* Permitted Clinical Actions Card */}
        <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 shadow-soft">
          <div className="flex items-center gap-2 border-b border-slate-100 dark:border-[#1e3840] pb-3 mb-3">
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

      {/* 3. EXECUTION PIPELINE TIMELINE (COLLAPSIBLE) */}
      <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-4 shadow-soft">
        <button
          type="button"
          onClick={() => setShowTimeline(!showTimeline)}
          className="flex w-full items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200 hover:text-teal-700 dark:hover:text-teal-300 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-teal-600 dark:text-teal-400" />
            <span>Execution Pipeline Timeline (9 Verification Stages)</span>
          </div>
          {showTimeline ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>

        {showTimeline && (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 pt-3 border-t border-slate-100 dark:border-[#1e3840]">
            {timelineStages.map((stage, idx) => (
              <div
                key={idx}
                className="rounded-xl border border-slate-200/80 dark:border-[#1e3840] bg-slate-50/60 dark:bg-[#0c1618] p-2.5 text-xs font-mono"
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
        )}
      </div>
    </div>
  )
}

export default ExplanationSection
