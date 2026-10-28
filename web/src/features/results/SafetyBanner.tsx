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

  let bannerStyle = 'border-[#A5D6A7] bg-[#E8F5E9] text-[#1B4D39] shadow-xs'
  let Icon = ShieldCheck
  let iconColor = 'text-[#2D6A4F]'

  if (isBlocked) {
    bannerStyle = 'border-red-300 bg-red-50 text-red-950 shadow-xs'
    Icon = AlertOctagon
    iconColor = 'text-red-600'
  } else if (isUnverified) {
    bannerStyle = 'border-purple-300 bg-purple-50 text-purple-950 shadow-xs'
    Icon = HelpCircle
    iconColor = 'text-purple-600'
  } else if (isAlerts) {
    bannerStyle = 'border-amber-300 bg-amber-50 text-amber-950 shadow-xs'
    Icon = AlertTriangle
    iconColor = 'text-amber-600'
  }

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`rounded-2xl border-2 p-5 ${bannerStyle}`}
    >
      <div className="flex items-start gap-3.5">
        <div className="shrink-0 mt-0.5">
          <Icon className={`h-7 w-7 ${iconColor}`} />
        </div>
        <div className="flex flex-col gap-1.5 flex-1">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <span className="font-mono text-sm font-black tracking-wide uppercase">
              {formattedVerdict}
            </span>
            <span className="text-[11px] font-mono px-2.5 py-0.5 rounded-full bg-white/80 border border-current/20 shadow-xs font-semibold">
              Evaluated: {checksRun} checks &bull; Skipped: {skippedCount}
            </span>
          </div>

          {isBlocked && (
            <p className="text-xs font-bold text-red-800 leading-relaxed">
              CRITICAL SAFETY CONTRAINDICATION: One or more proposed treatments are strictly blocked by deterministic clinical safety rules. Do NOT administer blocked medications.
            </p>
          )}

          {isUnverified && (
            <p className="text-xs font-bold text-purple-800 leading-relaxed">
              SAFETY CHECKS UNVERIFIED: Missing, incomplete, or unknown patient clinical data prevented full rule execution. System failed closed to prevent unverified treatment.
            </p>
          )}

          {isAlerts && (
            <p className="text-xs font-bold text-amber-900 leading-relaxed">
              CLINICAL SAFETY ALERTS TRIGGERED: One or more high or moderate alerts require clinician attention and documented override.
            </p>
          )}

          {!isBlocked && !isUnverified && !isAlerts && (
            <p className="text-xs font-medium text-[#1B4D39] leading-relaxed">
              No contraindications or active alerts triggered within currently loaded formulary and ruleset coverage.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

