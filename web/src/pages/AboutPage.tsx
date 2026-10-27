import React from 'react'
import { AlertTriangle, ShieldCheck } from 'lucide-react'
import { SplitText, BlurText, SpotlightCard } from '@/components/reactbits'
import { MANDATORY_DISCLAIMER } from '@/lib/wording'

export const AboutPage: React.FC = () => {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8 border-b border-slate-800/80 pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          <SplitText text="System Architecture & Limitations" />
        </h1>
        <div className="mt-1 text-sm text-slate-400">
          <BlurText text="Core design principles (R1–R12), safety properties, known limitations, and model cards." />
        </div>
      </div>

      <div className="mb-8 rounded-xl border border-amber-500/30 bg-amber-500/10 p-6 text-amber-200">
        <div className="flex items-center gap-3 mb-2">
          <AlertTriangle className="h-6 w-6 text-amber-400" />
          <h2 className="text-base font-bold uppercase tracking-wider text-amber-300">Clinical Disclaimer</h2>
        </div>
        <p className="text-sm font-semibold">{MANDATORY_DISCLAIMER}</p>
        <p className="mt-2 text-xs text-amber-200/80 leading-relaxed">
          TriageRAG is a research prototype exploring machine-verified deterministic safety architectures for emergency triage decision support. It is not licensed, cleared, or approved as medical device software. Under no circumstances should it be used for clinical decision-making.
        </p>
      </div>

      <SpotlightCard className="border-slate-800 bg-slate-900/60 mb-6">
        <div className="flex items-center gap-2 border-b border-slate-800 pb-3 mb-4">
          <ShieldCheck className="h-5 w-5 text-teal-400" />
          <h2 className="text-sm font-semibold text-slate-200">Core Architecture Invariants (R1–R12)</h2>
        </div>
        <ul className="space-y-2 text-xs text-slate-300 list-disc list-inside">
          <li><strong>R1: Code decides; the LLM explains.</strong> All scores, contraindications, and dose math are deterministic.</li>
          <li><strong>R2: Fail closed.</strong> Missing, unknown, or unresolved data yields UNVERIFIED, never clear.</li>
          <li><strong>R3: No invented clinical facts.</strong> Every rule, alias, and limit carries explicit provenance.</li>
          <li><strong>R4: Unknown is first-class.</strong> Tri-state Measured[T] and lookback timestamps everywhere.</li>
          <li><strong>R8: Decimal-only clinical math.</strong> Fixed-point precision with magnitude guards; no IEEE 754 floats.</li>
          <li><strong>R11: No override of BLOCK.</strong> No code path may approve or override a BLOCK contraindication.</li>
        </ul>
      </SpotlightCard>
    </div>
  )
}
