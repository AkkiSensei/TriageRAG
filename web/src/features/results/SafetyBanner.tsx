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

  let bannerStyle = 'border-teal-500/50 bg-teal-950/40 text-teal-200'
  let Icon = ShieldCheck
  let iconColor = 'text-teal-400'

  if (isBlocked) {
    bannerStyle = 'border-red-500/70 bg-red-950/50 text-red-200 shadow-[0_0_20px_rgba(239,68,68,0.25)]'
    Icon = AlertOctagon
    iconColor = 'text-red-400'
  } else if (isUnverified) {
    bannerStyle = 'border-purple-500/70 bg-purple-950/50 text-purple-200 shadow-[0_0_20px_rgba(139,92,246,0.2)]'
    Icon = HelpCircle
    iconColor = 'text-purple-400'
  } else if (isAlerts) {
    bannerStyle = 'border-amber-500/70 bg-amber-950/50 text-amber-200 shadow-[0_0_20px_rgba(245,158,11,0.2)]'
    Icon = AlertTriangle
    iconColor = 'text-amber-400'
  }

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`rounded-xl border-2 p-5 ${bannerStyle}`}
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
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-900/80 border border-slate-700/60">
              Evaluated: {checksRun} checks &bull; Skipped: {skippedCount}
            </span>
          </div>

          {isBlocked && (
            <p className="text-xs font-semibold text-red-300">
              CRITICAL SAFETY CONTRAINDICATION: One or more proposed treatments are strictly blocked by deterministic clinical safety rules. Do NOT administer blocked medications.
            </p>
          )}

          {isUnverified && (
            <p className="text-xs font-semibold text-purple-300">
              SAFETY CHECKS UNVERIFIED: Missing, incomplete, or unknown patient clinical data prevented full rule execution. System failed closed to prevent unverified treatment.
            </p>
          )}

          {isAlerts && (
            <p className="text-xs font-medium text-amber-300">
              CLINICAL SAFETY ALERTS TRIGGERED: One or more high or moderate alerts require clinician attention and documented override.
            </p>
          )}

          {!isBlocked && !isUnverified && !isAlerts && (
            <p className="text-xs text-teal-300">
              No contraindications or active alerts triggered within currently loaded formulary and ruleset coverage.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
