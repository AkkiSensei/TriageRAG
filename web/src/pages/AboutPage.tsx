import { AlertTriangle, ShieldCheck, FileCode, Scale } from 'lucide-react'
import { SplitText, BlurText, SpotlightCard } from '@/components/reactbits'
import { MANDATORY_DISCLAIMER } from '@/lib/wording'

export const AboutPage: React.FC = () => {
  const rules = [
    {
      id: 'R1',
      title: 'Code decides; the LLM explains.',
      desc: 'All scores, alerts, dose math, drug identity, and verdicts are computed by deterministic, pure Python code. The LLM only emits draft protocol plans which are machine-verified.',
    },
    {
      id: 'R2',
      title: 'Fail closed.',
      desc: 'Missing, unknown, or unresolved data yields UNVERIFIED, never clear. "No rule fired" means "no rule in this ruleset fired", not "safe".',
    },
    {
      id: 'R3',
      title: 'No invented clinical facts.',
      desc: 'Every rule, alias, formulary limit, and score table carries explicit Provenance. Author-drafted rules are marked UNSOURCED DRAFT and PLACEHOLDER_UNRETRIEVED.',
    },
    {
      id: 'R4',
      title: 'Unknown is first-class.',
      desc: 'Tri-state Measured[T] (measured, estimated, unknown) is used for all vitals and physical quantities. Lookbacks use absolute timestamps.',
    },
    {
      id: 'R5',
      title: 'LLM-optional fallback mode.',
      desc: 'If the LLM or vector index is offline, the full EngineReport and extractive protocol text still render deterministically.',
    },
    {
      id: 'R6',
      title: 'Layer isolation enforced by CI.',
      desc: 'import-linter guarantees that the clinical engine cannot import LLM packages, retrieval layers, API adapters, or UI frameworks.',
    },
    {
      id: 'R7',
      title: 'Untrusted input isolation.',
      desc: 'chief_complaint_untrusted is displayed to the clinician but by default is NEVER passed to the LLM, retrieval, or engine.',
    },
    {
      id: 'R8',
      title: 'Decimal-only clinical math.',
      desc: 'Fixed-point Decimal math with 10x/1000x magnitude guards; IEEE 754 floating point arithmetic is strictly forbidden.',
    },
    {
      id: 'R9',
      title: 'Synthetic corpus guarantee.',
      desc: 'Bundled protocols are original synthetic text labeled with SYNTHETIC watermarks and contain zero numeric doses.',
    },
    {
      id: 'R10',
      title: 'Measured, not claimed.',
      desc: 'CI fails on any missed BLOCK/HIGH case in golden suites. Golden recall verifies implementation correctness against rules, not clinical efficacy.',
    },
    {
      id: 'R11',
      title: 'No override of BLOCK.',
      desc: 'No code path or UI action may approve or override a BLOCK alert. HIGH severity alerts require an explicit logged justification.',
    },
    {
      id: 'R12',
      title: 'Pure determinism.',
      desc: 'The decision engine is pure and stateless. Ordering is stable, time is injected via Clock, and the registry is immutable.',
    },
  ]

  const adrs = [
    {
      id: 'ADR 0001',
      title: 'Separation of LLM Drafting from Deterministic Engine Verification',
      status: 'Accepted',
      summary: 'Decoupled generation from decision-making to guarantee safety invariants.',
    },
    {
      id: 'ADR 0002',
      title: 'Fixed-Point Decimal Arithmetic for Clinical Mathematics',
      status: 'Accepted',
      summary: 'Prohibited binary floating-point representation for dosages and vitals.',
    },
    {
      id: 'ADR 0003',
      title: 'Cryptographic SHA-256 Audit Chain with Tamper-Evident Hashing',
      status: 'Accepted',
      summary: 'Linked every triage decision and override to its cryptographic pre-image.',
    },
    {
      id: 'ADR 0004',
      title: 'Multiprocessing-Safe File-Locked Append-Only Audit Logger',
      status: 'Accepted',
      summary: 'Prevented race conditions and lock contention in concurrent clinical environments.',
    },
    {
      id: 'ADR 0005',
      title: 'Clinical UX Safety Architecture: UI Shows, Never Decides',
      status: 'Accepted',
      summary: 'Safety information is never animated or delayed; zero client-side clinical math; bare CLEAR prohibited.',
    },
  ]

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8 border-b border-slate-800/80 pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          <SplitText text="System Architecture & Limitations" />
        </h1>
        <div className="mt-1 text-sm text-slate-400">
          <BlurText text="Comprehensive specifications, safety UX principles, Architectural Decision Records (ADRs), and known research limitations." />
        </div>
      </div>

      {/* Mandatory Disclaimer */}
      <div className="mb-8 rounded-xl border border-amber-500/30 bg-amber-500/10 p-5 text-amber-200">
        <div className="flex items-center gap-3 mb-2">
          <AlertTriangle className="h-6 w-6 text-amber-400 shrink-0" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-amber-300">
            Mandatory Non-Negotiable Notice
          </h2>
        </div>
        <p className="text-sm font-semibold">{MANDATORY_DISCLAIMER}</p>
        <p className="mt-2 text-xs text-amber-200/80 leading-relaxed">
          TriageRAG is a research software prototype built to study deterministic verification architectures for AI decision support. It is not licensed or cleared as medical software under FDA, CE-MDR, or MHRA frameworks. It must never be used for diagnosis, clinical triage, or patient treatment.
        </p>
      </div>

      {/* Non-Negotiable Rules R1-R12 Grid */}
      <div className="mb-10">
        <div className="flex items-center gap-2 mb-4">
          <ShieldCheck className="h-5 w-5 text-teal-400" />
          <h2 className="text-base font-bold text-slate-100">Core Architecture Invariants (Rules R1&ndash;R12)</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rules.map((r) => (
            <SpotlightCard key={r.id} className="border-slate-800 bg-slate-900/60 p-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded bg-teal-500/10 border border-teal-500/30 font-mono text-xs font-bold text-teal-300">
                    {r.id}
                  </span>
                  <h3 className="text-xs font-bold text-slate-200">{r.title}</h3>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">{r.desc}</p>
              </div>
            </SpotlightCard>
          ))}
        </div>
      </div>

      {/* Known Limitations */}
      <div className="mb-10 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <div className="flex items-center gap-2 mb-4 border-b border-slate-800 pb-3">
          <Scale className="h-5 w-5 text-amber-400" />
          <h2 className="text-base font-bold text-slate-100">Declared Software Limitations</h2>
        </div>

        <ul className="space-y-3 text-xs text-slate-300">
          <li className="flex items-start gap-2">
            <span className="font-mono text-amber-400 font-bold shrink-0">&bull;</span>
            <div>
              <strong>Unsourced Draft Ruleset:</strong> All bundled rules, aliases, and formulary limits are software hypotheses authored for pipeline testing. They have not been reviewed by a panel of clinicians.
            </div>
          </li>
          <li className="flex items-start gap-2">
            <span className="font-mono text-amber-400 font-bold shrink-0">&bull;</span>
            <div>
              <strong>Circular Golden Set Recall:</strong> Golden set 100% recall proves that the Python implementation correctly evaluates the written rules; it does NOT prove the rules themselves are clinically optimal.
            </div>
          </li>
          <li className="flex items-start gap-2">
            <span className="font-mono text-amber-400 font-bold shrink-0">&bull;</span>
            <div>
              <strong>Physiological Early Warning Score &ne; Triage Category:</strong> NEWS2/PEWS calculate physiological deterioration risk; they do not dictate emergency severity index (ESI) triage bands.
            </div>
          </li>
          <li className="flex items-start gap-2">
            <span className="font-mono text-amber-400 font-bold shrink-0">&bull;</span>
            <div>
              <strong>Synthetic Corpus Only:</strong> Emergency protocol text is synthetic and devoid of numerical dosing guidelines to prevent accidental clinical adoption.
            </div>
          </li>
        </ul>
      </div>

      {/* Architectural Decision Records (ADR) Index */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <div className="flex items-center gap-2 mb-4 border-b border-slate-800 pb-3">
          <FileCode className="h-5 w-5 text-teal-400" />
          <h2 className="text-base font-bold text-slate-100">Architectural Decision Records (ADRs)</h2>
        </div>

        <div className="grid grid-cols-1 gap-3">
          {adrs.map((adr) => (
            <div
              key={adr.id}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs"
            >
              <div className="flex flex-col gap-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-teal-400">{adr.id}</span>
                  <span className="font-semibold text-slate-200">{adr.title}</span>
                </div>
                <span className="text-[11px] text-slate-400">{adr.summary}</span>
              </div>
              <span className="rounded bg-teal-950 border border-teal-800 px-2 py-0.5 text-[10px] font-mono font-bold text-teal-300 uppercase">
                {adr.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
