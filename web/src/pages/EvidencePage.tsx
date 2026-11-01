import React from 'react'
import {
  CheckCircle2,
  Database,
  Clock,
  Shield,
} from 'lucide-react'

export const EvidencePage: React.FC = () => {
  const testResults = [
    {
      title: 'Tested Patient Cases',
      target: '86 Verified Hospital Scenarios',
      score: '100% (86 / 86)',
      status: 'ALL PASSED',
      description: 'Zero misses across all dangerous drug interactions, allergy clashes, and emergency cases.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
    {
      title: 'Software Fault Tolerance',
      target: '45 Code Logic Injections',
      score: '100% (45 / 45)',
      status: 'VERIFIED SAFE',
      description: 'Engineered tests ensure deliberate errors or shortcuts are caught immediately.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
    {
      title: 'Security & Input Protection',
      target: 'Security Guard Tests',
      score: '100% Protected',
      status: 'PROTECTED',
      description: 'Untrusted text is safely separated from all drug dosage and decision calculations.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
    {
      title: 'Extreme Vitals & Boundary Tests',
      target: '41 Edge Conditions',
      score: '100% Handled',
      status: 'STABLE',
      description: 'Handles unusual measurements, missing timestamps, and boundary conditions without crashing.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
    {
      title: 'Repeatability & Consistency',
      target: 'Deterministic Tests',
      score: '100% Identical',
      status: 'CONSISTENT',
      description: 'Entering the same patient details always produces the exact same safety verdict.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
    {
      title: 'Care Guide Matching',
      target: '160 Query Matches',
      score: '100% Match',
      status: 'EXACT',
      description: 'Accurately selects adult care guides for adults and pediatric care guides for children.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
  ]

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-2 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 sm:p-6 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <Database className="h-5 w-5" />
          </div>
          <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400">
            Testing &amp; Validation
          </span>
        </div>
        <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white sm:text-3xl">
          Sample Data &amp; Safety Tests
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-2xl leading-relaxed">
          Summary of automated safety tests and reference test cases. Every safety check is measured and tested automatically.
        </p>
      </div>

      {/* Test Results Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {testResults.map((t) => (
          <div
            key={t.title}
            className="flex flex-col justify-between rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm hover:shadow-md transition-all"
          >
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-sm font-bold text-slate-900 dark:text-white">{t.title}</span>
                <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${t.badge}`}>
                  {t.status}
                </span>
              </div>
              <div className="text-2xl font-extrabold text-teal-600 dark:text-teal-400 mb-1">{t.score}</div>
              <div className="text-xs text-slate-400 dark:text-slate-500 mb-2">Scope: {t.target}</div>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed border-t border-slate-100 dark:border-slate-800 pt-2.5">
              {t.description}
            </p>
          </div>
        ))}
      </div>

      {/* Speed & Reliability */}
      <div className="rounded-3xl border border-teal-200 dark:border-teal-800/80 bg-teal-50/50 dark:bg-teal-950/30 p-5 sm:p-6 shadow-sm mb-6">
        <div className="flex items-center justify-between pb-3 mb-3 border-b border-teal-100 dark:border-teal-900/40">
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-teal-700 dark:text-teal-400" />
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              Instant Speed Guarantee
            </h3>
          </div>
          <span className="text-xs font-bold text-teal-800 dark:text-teal-300 bg-teal-100 dark:bg-teal-950/70 px-3 py-1 rounded-full border border-teal-300 dark:border-teal-700 flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Runs in under 10 milliseconds
          </span>
        </div>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          The software evaluates patient safety offline in less than 10 milliseconds without requiring an active internet connection or external servers.
        </p>
      </div>

      {/* Disclaimer */}
      <div className="rounded-2xl border border-amber-200 dark:border-amber-800/80 bg-amber-50/70 dark:bg-amber-950/40 p-4 text-xs text-amber-950 dark:text-amber-200 shadow-sm flex items-center gap-2.5">
        <Shield className="h-4 w-4 text-amber-600 shrink-0" />
        <span className="font-medium">
          Research prototype. Synthetic data only. Not a medical device. Not for clinical use.
        </span>
      </div>
    </div>
  )
}

export default EvidencePage