import React from 'react'
import { AlertOctagon, HelpCircle, AlertTriangle, ShieldCheck } from 'lucide-react'
import { formatSafetyVerdict, assertNoBareClear } from '@/lib/wording'
import type { EngineReport } from '@/lib/api'

interface SafetyBannerProps {
  report: EngineReport
}

export const SafetyBanner: React.FC<SafetyBannerProps> = ({ report }) => {
  const verdict = report.verdict
  const checksRun = report.checks_run ?? 0
  const skippedCount = report.checks_skipped?.length ?? 0
  const formattedVerdict = formatSafetyVerdict(verdict, checksRun)

  // Ensure no bare CLEAR
  if (!assertNoBareClear(formattedVerdict)) {
    throw new Error('UX Safety Violation: bare CLEAR detected in SafetyBanner')
  }

  const isBlocked = verdict === 'BLOCKED'
  const isUnverified = verdict === 'UNVERIFIED'
  const isAlerts = verdict === 'CHECKED_ALERTS'

  let bannerStyle = 'border-teal-300 bg-gradient-to-r from-teal-50 via-white to-teal-50/70 text-teal-950 shadow-soft dark:border-teal-700/80 dark:bg-gradient-to-r dark:from-teal-950/40 dark:via-[#132226] dark:to-teal-950/30 dark:text-teal-100'
  let Icon = ShieldCheck
  let iconColor = 'text-teal-700 dark:text-teal-400'
  let badgeStyle = 'bg-teal-100/90 text-teal-900 border-teal-200 dark:bg-teal-950/60 dark:text-teal-200 dark:border-teal-700'

  if (isBlocked) {
    bannerStyle = 'border-rose-400 bg-gradient-to-r from-rose-50 via-white to-rose-50/70 text-rose-950 shadow-soft dark:border-rose-700/80 dark:bg-gradient-to-r dark:from-rose-950/40 dark:via-[#132226] dark:to-rose-950/30 dark:text-rose-100'
    Icon = AlertOctagon
    iconColor = 'text-rose-600 dark:text-rose-400'
    badgeStyle = 'bg-rose-100 text-rose-900 border-rose-300 dark:bg-rose-950/60 dark:text-rose-200 dark:border-rose-700'
  } else if (isUnverified) {
    bannerStyle = 'border-violet-300 bg-gradient-to-r from-violet-50 via-white to-violet-50/70 text-violet-950 shadow-soft dark:border-violet-700/80 dark:bg-gradient-to-r dark:from-violet-950/40 dark:via-[#132226] dark:to-violet-950/30 dark:text-violet-100'
    Icon = HelpCircle
    iconColor = 'text-violet-600 dark:text-violet-400'
    badgeStyle = 'bg-violet-100 text-violet-900 border-violet-300 dark:bg-violet-950/60 dark:text-violet-200 dark:border-violet-700'
  } else if (isAlerts) {
    bannerStyle = 'border-amber-300 bg-gradient-to-r from-amber-50 via-white to-amber-50/70 text-amber-950 shadow-soft dark:border-amber-700/80 dark:bg-gradient-to-r dark:from-amber-950/40 dark:via-[#132226] dark:to-amber-950/30 dark:text-amber-100'
    Icon = AlertTriangle
    iconColor = 'text-amber-600 dark:text-amber-400'
    badgeStyle = 'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/60 dark:text-amber-200 dark:border-amber-700'
  }

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`rounded-3xl border-2 p-5 sm:p-6 ${bannerStyle} transition-all`}
    >
      <div className="flex items-start gap-4">
        <div className="shrink-0 mt-0.5">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white dark:bg-[#0c1618] shadow-soft-sm border border-current/10 dark:border-slate-700">
            <Icon className={`h-6 w-6 ${iconColor}`} />
          </div>
        </div>
        <div className="flex flex-col gap-2 flex-1">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="font-mono text-sm sm:text-base font-black tracking-wide uppercase">
              {formattedVerdict}
            </span>
            <span className={`text-[11px] font-mono px-3 py-1 rounded-full border shadow-soft-sm font-semibold ${badgeStyle}`}>
              Evaluated: {checksRun} checks &bull; Skipped: {skippedCount}
            </span>
          </div>

          {isBlocked && (
            <p className="text-xs sm:text-sm font-bold text-rose-900 dark:text-rose-200 leading-relaxed">
              CRITICAL SAFETY CONTRAINDICATION: One or more proposed treatments are strictly blocked by deterministic clinical safety rules. Do NOT administer blocked medications.
            </p>
          )}

          {isUnverified && (
            <p className="text-xs sm:text-sm font-bold text-violet-900 dark:text-violet-200 leading-relaxed">
              SAFETY CHECKS UNVERIFIED: Missing, incomplete, or unknown patient clinical data prevented full rule execution. System failed closed to prevent unverified treatment.
            </p>
          )}

          {isAlerts && (
            <p className="text-xs sm:text-sm font-bold text-amber-900 dark:text-amber-200 leading-relaxed">
              CLINICAL SAFETY ALERTS TRIGGERED: One or more high or moderate alerts require clinician attention and documented override.
            </p>
          )}

          {!isBlocked && !isUnverified && !isAlerts && (
            <p className="text-xs sm:text-sm font-medium text-teal-900 dark:text-teal-200 leading-relaxed">
              No contraindications or active alerts triggered within currently loaded formulary and ruleset coverage.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default SafetyBanner
