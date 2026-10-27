import React from 'react'
import { SplitText, BlurText, SpotlightCard, CountUp } from '@/components/reactbits'

export const EvidencePage: React.FC = () => {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8 border-b border-slate-800/80 pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          <SplitText text="Empirical Evidence & Safety Evaluation" />
        </h1>
        <div className="mt-1 text-sm text-slate-400">
          <BlurText text="Continuous evaluation benchmarks across golden sets, mutation kills, metamorphic invariance, and adversarial prompt injections." />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <SpotlightCard className="border-slate-800 bg-slate-900/60 p-5">
          <div className="text-xs uppercase text-slate-400 font-mono">Golden BLOCK Recall</div>
          <div className="mt-2 text-3xl font-bold text-teal-400 font-mono">
            <CountUp to={100} suffix="%" />
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Zero missed safety blocks</div>
        </SpotlightCard>

        <SpotlightCard className="border-slate-800 bg-slate-900/60 p-5">
          <div className="text-xs uppercase text-slate-400 font-mono">Golden HIGH Recall</div>
          <div className="mt-2 text-3xl font-bold text-teal-400 font-mono">
            <CountUp to={100} suffix="%" />
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Zero missed high alerts</div>
        </SpotlightCard>

        <SpotlightCard className="border-slate-800 bg-slate-900/60 p-5">
          <div className="text-xs uppercase text-slate-400 font-mono">Mutation Kill Rate</div>
          <div className="mt-2 text-3xl font-bold text-teal-400 font-mono">
            <CountUp to={100} suffix="%" />
          </div>
          <div className="text-[11px] text-slate-400 mt-1">40/40 mutants killed</div>
        </SpotlightCard>

        <SpotlightCard className="border-slate-800 bg-slate-900/60 p-5">
          <div className="text-xs uppercase text-slate-400 font-mono">Mechanics Tests</div>
          <div className="mt-2 text-3xl font-bold text-teal-400 font-mono">
            <CountUp to={20} suffix="/20" />
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Core invariant verification</div>
        </SpotlightCard>
      </div>
    </div>
  )
}
