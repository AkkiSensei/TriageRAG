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

  let bannerStyle = 'border-teal-300 bg-gradient-to-r from-teal-50 via-white to-teal-50/70 text-teal-950 shadow-soft'
  let Icon = ShieldCheck
  let iconColor = 'text-teal-700'
  let badgeStyle = 'bg-teal-100/90 text-teal-900 border-teal-200'

  if (isBlocked) {
    bannerStyle = 'border-rose-400 bg-gradient-to-r from-rose-50 via-white to-rose-50/70 text-rose-950 shadow-soft'
    Icon = AlertOctagon
    iconColor = 'text-rose-600'
    badgeStyle = 'bg-rose-100 text-rose-900 border-rose-300'
  } else if (isUnverified) {
    bannerStyle = 'border-violet-300 bg-gradient-to-r from-violet-50 via-white to-violet-50/70 text-violet-950 shadow-soft'
    Icon = HelpCircle
    iconColor = 'text-violet-600'
    badgeStyle = 'bg-violet-100 text-violet-900 border-violet-300'
  } else if (isAlerts) {
    bannerStyle = 'border-amber-300 bg-gradient-to-r from-amber-50 via-white to-amber-50/70 text-amber-950 shadow-soft'
    Icon = AlertTriangle
    iconColor = 'text-amber-600'
    badgeStyle = 'bg-amber-100 text-amber-900 border-amber-300'
  }

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`rounded-3xl border-2 p-5 sm:p-6 ${bannerStyle} transition-all`}
    >
      <div className="flex items-start gap-4">
        <div className="shrink-0 mt-0.5">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white shadow-soft-sm border border-current/10">
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
            <p className="text-xs sm:text-sm font-bold text-rose-900 leading-relaxed">
              CRITICAL SAFETY CONTRAINDICATION: One or more proposed treatments are strictly blocked by deterministic clinical safety rules. Do NOT administer blocked medications.
            </p>
          )}

          {isUnverified && (
            <p className="text-xs sm:text-sm font-bold text-violet-900 leading-relaxed">
              SAFETY CHECKS UNVERIFIED: Missing, incomplete, or unknown patient clinical data prevented full rule execution. System failed closed to prevent unverified treatment.
            </p>
          )}

          {isAlerts && (
            <p className="text-xs sm:text-sm font-bold text-amber-900 leading-relaxed">
              CLINICAL SAFETY ALERTS TRIGGERED: One or more high or moderate alerts require clinician attention and documented override.
            </p>
          )}

          {!isBlocked && !isUnverified && !isAlerts && (
            <p className="text-xs sm:text-sm font-medium text-teal-900 leading-relaxed">
              No contraindications or active alerts triggered within currently loaded formulary and ruleset coverage.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default SafetyBanner
