import React from 'react'
import { AlertTriangle, ShieldCheck } from 'lucide-react'
import { MANDATORY_DISCLAIMER } from '@/lib/wording'

export const Footer: React.FC = () => {
  return (
    <footer className="w-full border-t border-slate-800/80 bg-slate-950/90 py-6 text-xs text-slate-400">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col gap-4">
        {/* Persistent Mandatory Disclaimer Banner */}
        <div className="flex items-start sm:items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-amber-300">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-400" />
          <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2">
            <span className="font-semibold uppercase tracking-wider text-[11px] text-amber-200">Mandatory Notice:</span>
            <span className="text-xs">{MANDATORY_DISCLAIMER}</span>
          </div>
        </div>

        {/* Footer Meta & Protocol Guarantees */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-teal-400" />
            <span>Deterministic Clinical Engine &bull; Pure In-Memory Verification &bull; No Overrides for BLOCK</span>
          </div>
          <div className="flex items-center gap-4 text-slate-400">
            <span>Decimal-only clinical math</span>
            <span>&bull;</span>
            <span>Cryptographic Audit Chain</span>
            <span>&bull;</span>
            <span className="font-mono text-slate-400">v0.1.0-alpha</span>
          </div>
        </div>
      </div>
    </footer>
  )
}
