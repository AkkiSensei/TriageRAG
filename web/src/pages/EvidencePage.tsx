import React from 'react'
import {
  LineChart,
  Clock,
} from 'lucide-react'

export const EvidencePage: React.FC = () => {

  const benchmarkMetrics = [
    {
      name: 'Shipped Golden Cases',
      target: '65 Reference Patients',
      score: '100% (65/65)',
      status: 'PASSED',
      description: 'Zero misses across all BLOCK and HIGH clinical interaction cases.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
    {
      name: 'Mutation Kill Score',
      target: '45 Injected Mutants',
      score: '100% (45/45)',
      status: 'KILLED',
      description: 'Every deliberate logic mutant (precedence flip, lookback bypass, dose float) killed.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
    {
      name: 'Adversarial Prompt Defense',
      target: '9 Hijack Attempts',
      score: '100% (9/9)',
      status: 'BLOCKED',
      description: 'Prompt injections quarantined from decision engine and groundings.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
    {
      name: 'Mechanics Edge Cases',
      target: '41 Boundary States',
      score: '100% (41/41)',
      status: 'PASSED',
      description: 'Tested across negative ages, future dose timestamps, and extreme vitals.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
    {
      name: 'Metamorphic Invariance',
      target: '3 Transformations',
      score: '100% (3/3)',
      status: 'PASSED',
      description: 'Order shuffling and synonym replacement produce byte-identical verdicts.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
    {
      name: 'Protocol Retrieval R@5',
      target: '160 Query Pairs',
      score: '100.0% R@5',
      status: 'OPTIMAL',
      description: '0.0000 Wrong-Protocol Rate with hard age-group population partitioning.',
      badge: 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700',
    },
  ]

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-2 rounded-3xl border border-[#d9e8e6] dark:border-[#1e3840] bg-gradient-to-r from-teal-50/40 dark:from-teal-950/30 via-white dark:via-[#132226] to-white dark:to-[#132226] p-5 sm:p-6 shadow-soft">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <LineChart className="h-4 w-4" />
          </div>
          <span className="text-xs font-mono uppercase tracking-widest text-teal-800 dark:text-teal-300 font-bold">
            Empirical Validation
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 font-semibold border border-teal-200 dark:border-teal-800">
            Rule R10 &bull; Measured, Not Claimed
          </span>
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
          Verification Benchmarks &amp; Evidence Matrix
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-2xl leading-relaxed">
          TriageRAG is governed by continuous empirical measurement.
          Below are the automated verification results across all 7 evaluation suites.
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {benchmarkMetrics.map((m) => (
          <div
            key={m.name}
            className="flex flex-col justify-between rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 shadow-soft hover:shadow-soft-lg transition-all"
          >
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-xs font-bold text-slate-900 dark:text-slate-100">{m.name}</span>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${m.badge}`}>
                  {m.status}
                </span>
              </div>
              <div className="text-2xl font-extrabold font-mono text-teal-700 dark:text-teal-400 mb-1">{m.score}</div>
              <div className="text-[11px] font-mono text-slate-400 dark:text-slate-500 mb-2">Scope: {m.target}</div>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed border-t border-slate-100 dark:border-[#1e3840] pt-2.5">
              {m.description}
            </p>
          </div>
        ))}
      </div>

      {/* Scale & Speed Guarantee */}
      <div className="rounded-3xl border border-teal-200 dark:border-teal-800/80 bg-gradient-to-r from-teal-50/50 dark:from-teal-950/30 via-white dark:via-[#132226] to-teal-50/20 dark:to-[#132226] p-5 sm:p-6 shadow-soft mb-6">
        <div className="flex items-center justify-between pb-3 mb-3 border-b border-teal-100 dark:border-[#1e3840]">
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-teal-700 dark:text-teal-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-100">
              Retrieval Scale Latency Benchmark
            </h3>
          </div>
          <span className="text-xs font-mono font-bold text-teal-800 dark:text-teal-300 bg-teal-100 dark:bg-teal-950/70 px-2.5 py-0.5 rounded-full border border-teal-300 dark:border-teal-700">
            p95 = 5.65 ms (&lt; 50 ms budget)
          </span>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
          Stress tested on 10,000 synthetic clinical guideline chunks using BM25 lexical search with medical acronym expansion. 95% of queries execute in under 6 milliseconds offline without GPU dependencies.
        </p>
      </div>

      {/* Limitations note */}
      <div className="rounded-2xl border border-amber-200 dark:border-amber-800/80 bg-amber-50/70 dark:bg-amber-950/40 p-4 text-xs text-amber-950 dark:text-amber-200 shadow-soft-sm">
        <span className="font-bold text-amber-900 dark:text-amber-300">Limitation Notice (Circular Recall): </span>
        <span className="text-amber-900/90 dark:text-amber-200 leading-relaxed font-medium">
          Passing 100% of golden cases certifies that the pure Python software faithfully executes the authored clinical rules. It does not certify real-world medical efficacy until human clinical pharmacologists sign off on the seed ruleset.
        </span>
      </div>
    </div>
  )
}

export default EvidencePage
