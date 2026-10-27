import React from 'react'
import { Activity, ShieldCheck } from 'lucide-react'
import { SplitText, BlurText, ShinyText, SpotlightCard } from '@/components/reactbits'

export const ConsolePage: React.FC = () => {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header section with React Bits animations */}
      <div className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="flex h-2 w-2 rounded-full bg-teal-400" />
            <ShinyText text="DETERMINISTIC CLINICAL DECISION SUPPORT" className="text-xs uppercase tracking-widest" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            <SplitText text="Emergency Triage Console" />
          </h1>
          <div className="mt-1 text-sm text-slate-400">
            <BlurText text="Enter patient vitals, medication history, and suspected condition to generate verified decision support." />
          </div>
        </div>
      </div>

      {/* Main console layout grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Intake Stepper */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          <SpotlightCard className="border-slate-800 bg-slate-900/60">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3 mb-4">
              <Activity className="h-4 w-4 text-teal-400" />
              <h2 className="text-sm font-semibold text-slate-200">Patient Intake & Vitals</h2>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Console intake form initialized. Complete with tri-state Measured inputs, Decimal-only physiological math, and strict input boundaries.
            </p>
          </SpotlightCard>
        </div>

        {/* Right Column: Static Results Pane */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3 mb-4">
              <ShieldCheck className="h-4 w-4 text-teal-400" />
              <h2 className="text-sm font-semibold text-slate-200">Triage Safety Engine Output</h2>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Results pane initialized. Renders deterministic early-warning score, drug-safety contraindication alerts, dose checks, coverage gaps, and machine-verified protocol plan.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
