import React from 'react'
import { HelpCircle, AlertCircle } from 'lucide-react'
import type { components } from '@/types/api'

export type SkippedCheck = components['schemas']['SkippedCheck']

interface SkippedChecksListProps {
  skippedChecks: SkippedCheck[]
}

export const SkippedChecksList: React.FC<SkippedChecksListProps> = ({ skippedChecks }) => {
  if (!skippedChecks || skippedChecks.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-purple-900/60 bg-purple-950/20 p-4">
      <div className="flex items-center justify-between border-b border-purple-900/40 pb-2">
        <div className="flex items-center gap-2">
          <HelpCircle className="h-4 w-4 text-purple-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-purple-200">
            What I Couldn&apos;t Check ({skippedChecks.length}) &mdash; R2 Fail Closed
          </h3>
        </div>
        <span className="text-[10px] font-mono text-purple-300/80">Missing Data Tripped</span>
      </div>

      <p className="text-xs text-purple-300/90 leading-relaxed">
        The following clinical rules could not be evaluated due to missing or unresolved patient fields. Under the fail-closed principle, these are flagged as unverified rather than assumed safe:
      </p>

      <div className="flex flex-col gap-2">
        {skippedChecks.map((check: SkippedCheck, idx: number) => (
          <div
            key={`${check.rule_id}-${idx}`}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-lg border border-purple-900/40 bg-slate-950/60 p-2.5 text-xs"
          >
            <div className="flex flex-col gap-0.5">
              <div className="flex items-center gap-2">
                <span className="font-mono font-semibold text-purple-200">{check.rule_id}</span>
                <span className="text-[10px] text-purple-400 font-mono">({check.rule_type})</span>
              </div>
              <span className="text-slate-400 text-[11px]">{check.reason}</span>
            </div>

            {check.missing_fields && check.missing_fields.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[10px] text-slate-400">Missing:</span>
                {check.missing_fields.map((f: string) => (
                  <span
                    key={f}
                    className="flex items-center gap-1 rounded bg-purple-900/40 border border-purple-800/60 px-1.5 py-0.5 text-[10px] font-mono text-purple-200"
                  >
                    <AlertCircle className="h-2.5 w-2.5" />
                    {f}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
