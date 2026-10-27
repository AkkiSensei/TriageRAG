import React from 'react'
import { ShieldAlert } from 'lucide-react'
import { SplitText, BlurText, SpotlightCard } from '@/components/reactbits'

export const RulesetPage: React.FC = () => {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8 border-b border-slate-800/80 pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          <SplitText text="Clinical Ruleset & Formulary Explorer" />
        </h1>
        <div className="mt-1 text-sm text-slate-400">
          <BlurText text="Browse deterministic contraindication rules, drug-drug interactions, and formulary limits with explicit provenance and audit status." />
        </div>
      </div>
      <SpotlightCard className="border-slate-800 bg-slate-900/60">
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3 mb-4">
          <ShieldAlert className="h-4 w-4 text-teal-400" />
          <h2 className="text-sm font-semibold text-slate-200">Rules Registry</h2>
        </div>
        <p className="text-xs text-slate-400">
          Filterable registry table with draft provenance badges and rule inspection drawer.
        </p>
      </SpotlightCard>
    </div>
  )
}
