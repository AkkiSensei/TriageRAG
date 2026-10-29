import React from 'react'
import { AlertTriangle, ShieldCheck, HeartPulse } from 'lucide-react'
import { MANDATORY_DISCLAIMER } from '@/lib/wording'

export const Footer: React.FC = () => {
  return (
    <footer className="w-full border-t border-[#d9e8e6] dark:border-[#1e3840] bg-white/80 dark:bg-[#132226]/80 backdrop-blur-sm py-6 text-xs text-slate-500 dark:text-slate-400">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col gap-4">
        {/* Persistent Mandatory Disclaimer Banner */}
        <div className="flex items-start sm:items-center gap-3.5 rounded-2xl border border-amber-200 dark:border-amber-800/60 bg-amber-50/80 dark:bg-amber-950/30 p-4 text-amber-900 dark:text-amber-200 shadow-soft-sm">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-900/60 text-amber-700 dark:text-amber-300">
            <AlertTriangle className="h-4 w-4" />
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2">
            <span className="font-bold uppercase tracking-wider text-[11px] text-amber-800 dark:text-amber-400">
              Mandatory Notice:
            </span>
            <span className="text-xs text-amber-950/90 dark:text-amber-200/90 leading-relaxed font-medium">
              {MANDATORY_DISCLAIMER}
            </span>
          </div>
        </div>

        {/* Footer Meta & Protocol Guarantees */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-slate-500 dark:text-slate-400">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-teal-600 dark:text-teal-400" />
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              Deterministic Clinical Engine &bull; Code Decides, LLM Explains &bull; Zero Override for BLOCK
            </span>
          </div>
          <div className="flex items-center gap-3 font-mono text-slate-500 dark:text-slate-400">
            <span className="flex items-center gap-1">
              <HeartPulse className="h-3 w-3 text-coral-500" />
              Decimal-only math
            </span>
            <span>&bull;</span>
            <span>SHA-256 Merkle Audit</span>
            <span>&bull;</span>
            <span className="font-bold text-teal-700 dark:text-teal-400">v0.1.0-clinical</span>
          </div>
        </div>
      </div>
    </footer>
  )
}

export default Footer
