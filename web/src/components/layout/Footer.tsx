import React from 'react'
import { AlertTriangle, ShieldCheck } from 'lucide-react'
import { MANDATORY_DISCLAIMER } from '@/lib/wording'

export const Footer: React.FC = () => {
  return (
    <footer className="w-full border-t border-[#E1E7E1] bg-white py-6 text-xs text-[#5C6B64]">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col gap-4">
        {/* Persistent Mandatory Disclaimer Banner */}
        <div className="flex items-start sm:items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-amber-900 shadow-xs">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600" />
          <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2">
            <span className="font-bold uppercase tracking-wider text-[11px] text-amber-800">Mandatory Notice:</span>
            <span className="text-xs text-amber-900/90 leading-relaxed">{MANDATORY_DISCLAIMER}</span>
          </div>
        </div>

        {/* Footer Meta & Protocol Guarantees */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-[#5C6B64]">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-[#2D6A4F]" />
            <span className="font-medium text-[#1A2421]">Deterministic Clinical Engine &bull; Pure In-Memory Verification &bull; No Overrides for BLOCK</span>
          </div>
          <div className="flex items-center gap-3 text-[#5C6B64] font-mono">
            <span>Decimal-only math</span>
            <span>&bull;</span>
            <span>Cryptographic Audit Chain</span>
            <span>&bull;</span>
            <span className="font-bold text-[#1A2421]">v0.1.0-alpha</span>
          </div>
        </div>
      </div>
    </footer>
  )
}

