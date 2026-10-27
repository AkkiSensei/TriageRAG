import React from 'react'
import { FileText } from 'lucide-react'
import { SplitText, BlurText, SpotlightCard } from '@/components/reactbits'

export const AuditPage: React.FC = () => {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8 border-b border-slate-800/80 pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          <SplitText text="Cryptographic Audit Trail" />
        </h1>
        <div className="mt-1 text-sm text-slate-400">
          <BlurText text="Inspect SHA-256 hash chains of all clinical evaluations, override decisions, and integrity verification." />
        </div>
      </div>
      <SpotlightCard className="border-slate-800 bg-slate-900/60">
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3 mb-4">
          <FileText className="h-4 w-4 text-teal-400" />
          <h2 className="text-sm font-semibold text-slate-200">Append-Only Audit Log</h2>
        </div>
        <p className="text-xs text-slate-400">
          Tamper-evident audit chain with one-click cryptographic hash verification.
        </p>
      </SpotlightCard>
    </div>
  )
}
