/**
 * Visual Directed Process Graph & Real-Time Activity Feed for LangGraph State Machine (ADR 0017).
 *
 * Safety Properties (Rule R1, Rule R2, Rule R7, Rule R11):
 * 1. Visual graph representation of the exact LangGraph topology (sequential stages, forks, and joins).
 * 2. Real-time event reflection: strictly updates from actual backend lifecycle SSE messages.
 *    Zero timers, zero artificial progression, zero fabricated delay.
 * 3. Privacy allowlist: safe summaries contain only operation counts/status codes,
 *    strictly forbidding patient identifiers, vitals, drugs, allergies, complaint narratives,
 *    and exception tracebacks.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertOctagon,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  Cpu,
  FileCheck,
  FileText,
  Filter,
  HelpCircle,
  Lock,
  RotateCw,
  Scale,
  ShieldAlert,
  ShieldCheck,
  SkipForward,
  Terminal,
  Workflow,
  X,
  XCircle,
} from 'lucide-react'
import type { TriageLifecycleEvent, StageStatus } from '@/types/execution'

// ---------------------------------------------------------------------------
// Node Metadata Catalog (Enforcing Rule R1, R2, R7, R11)
// ---------------------------------------------------------------------------

interface NodeMeta {
  index: string
  tag: string
  rule: string
  ruleRef: string
  description: string
  invariant: string
}

const NODE_CATALOG: Record<string, NodeMeta> = {
  validation: {
    index: '01',
    tag: 'SCHEMA GATE',
    rule: 'Rule R1 · Strict Schema Ingress',
    ruleRef: 'ADR 0017 · Pydantic Input Boundary',
    description: 'Validates incoming patient payload against strict Pydantic clinical models. Rejects malformed types, invalid units, and non-canonical codes before graph execution.',
    invariant: 'Untrusted input is validated deterministically; invalid payloads never enter graph state.',
  },
  normalise: {
    index: '02',
    tag: 'NORMALIZER',
    rule: 'Rule R4 · Measured[T] Tri-State',
    ruleRef: 'ADR 0003 · Vitals Normalization',
    description: 'Converts physiological observations into canonical units. Calculates Early Warning Score (NEWS2/PEWS) and maps vital sign trigger flags.',
    invariant: 'Missing vitals remain strictly Unknown (fail-closed); never imputed as normal.',
  },
  intake_safety_checks: {
    index: '03',
    tag: 'SAFETY INTERLOCK',
    rule: 'Rule R8 & R11 · Baseline Safety',
    ruleRef: 'ADR 0002 · Decimal-Only Engine Math',
    description: 'Evaluates deterministic contraindications, drug-drug interactions (DDIs), and allergy cross-sensitivities against current active medications.',
    invariant: 'Safety rules evaluated in pure deterministic code; zero LLM influence.',
  },
  retrieve: {
    index: '04',
    tag: 'DECISION ROUTER',
    rule: 'Rule R9 · Synthetic Protocols',
    ruleRef: 'ADR 0004 · Lexical BM25 Retrieval',
    description: 'Searches local BM25 protocol index using clinical aliases and vital flags. Routes dynamically to Plan Drafting if chunks exist, or Abstain Fallback if empty.',
    invariant: 'Zero network retrieval; 100% offline synthetic emergency protocols.',
  },
  draft_plan: {
    index: '05a',
    tag: 'LLM SYNTHESIS',
    rule: 'Rule R1 · LLM Proposes Only',
    ruleRef: 'ADR 0005 · Constrained Generation',
    description: 'LLM drafts candidate clinical action steps extracted strictly from retrieved protocol chunks. Emits structured PlanDraft without authorization.',
    invariant: 'LLM never decides; all steps remain unapproved until verified by deterministic code in Node 6.',
  },
  abstain_fallback: {
    index: '05b',
    tag: 'FAIL-CLOSED FALLBACK',
    rule: 'Rule R2 · Fail-Closed Boundary',
    ruleRef: 'ADR 0011 · Absence of Guidance',
    description: 'Triggered when protocol retrieval yields no verified match. Emits an empty draft plan with UNVERIFIED triage disposition.',
    invariant: 'Absence of verified guidance never defaults to clear; fail closed.',
  },
  verify: {
    index: '06',
    tag: 'DETERMINISTIC VERIFIER',
    rule: 'Rule R1, R8, R11 · Machine Verifier',
    ruleRef: 'ADR 0006 · Pass 2 Action Verification',
    description: 'Re-evaluates every proposed draft step against the deterministic safety engine: checks dose limits, contraindications, and drug interactions with Decimal precision.',
    invariant: 'Routes dynamically to BLOCK Seal if any BLOCK alert fired, UNVERIFIED Seal if data is missing, or VERIFIED Seal if clear.',
  },
  block_seal: {
    index: '07a',
    tag: 'DISPOSITION SEAL',
    rule: 'Rule R11 · Non-Overridable BLOCK',
    ruleRef: 'ADR 0012 · Hard Safety Interlocks',
    description: 'Hard clinical stop. A lethal contraindication (e.g. PDE5 inhibitor with nitrates) was detected. Seals overall verdict as BLOCK.',
    invariant: 'No clinician override path exists. Contraindicated steps are permanently excluded from administration.',
  },
  unverified_seal: {
    index: '07b',
    tag: 'DISPOSITION SEAL',
    rule: 'Rule R2 · Coverage Boundary',
    ruleRef: 'ADR 0011 · Unverified State Boundary',
    description: 'Patient has unmeasured vitals, unknown allergy history, or unverified medications. Seals overall verdict as UNVERIFIED.',
    invariant: 'Missing data cannot be assumed safe; prompts clinician for manual verification.',
  },
  verified_seal: {
    index: '07c',
    tag: 'DISPOSITION SEAL',
    rule: 'Rule R1 · Deterministic Clearance',
    ruleRef: 'ADR 0007 · Clearance Lattice',
    description: 'All intake checks passed and all proposed steps met formulary dosage, allergy, and interaction limits. Seals verdict as CHECKED_CLEAR or CHECKED_ALERTS.',
    invariant: 'Clearance granted solely by deterministic verification engine.',
  },
  audit: {
    index: '08',
    tag: 'SECURITY SEAL',
    rule: 'Rule R12 · Tamper-Evident Ledger',
    ruleRef: 'ADR 0010 · SHA-256 Audit Chain',
    description: 'Appends immutable SHA-256 hash record of normalized patient, rule evaluations, engine verdict, and clinical plan to the tamper-evident audit chain.',
    invariant: 'Cryptographic integrity prevents post-hoc alterations of triage decisions.',
  },
  explain: {
    index: '09',
    tag: 'REPORT COMPILER',
    rule: 'Rule R1 & R7 · Clinical Presentation',
    ruleRef: 'ADR 0008 · EngineReport Synthesis',
    description: 'Assembles the final EngineReport, verified medication actions, confidence score, and untrusted narrative boundary into the structured TriageResponse.',
    invariant: 'Chief complaint narrative remains sanitized and quarantined from engine decision paths.',
  },
}

// ---------------------------------------------------------------------------
// SVG Directed Graph Edges & Routing Components
// ---------------------------------------------------------------------------

const VerticalEdge: React.FC<{
  active?: boolean
  completed?: boolean
  label?: string
}> = ({ active, completed, label }) => (
  <div className="flex flex-col items-center my-0.5 select-none relative" aria-hidden="true">
    {label && (
      <span className="text-[9px] font-mono font-semibold text-slate-400 mb-0.5">
        {label}
      </span>
    )}
    <svg width="24" height="28" viewBox="0 0 24 28" fill="none" className="overflow-visible">
      {/* Background track */}
      <line x1="12" y1="0" x2="12" y2="20" stroke="#334155" strokeWidth="2" />
      {/* Dynamic Trace */}
      <line
        x1="12"
        y1="0"
        x2="12"
        y2="20"
        stroke={active ? '#38bdf8' : completed ? '#10b981' : '#475569'}
        strokeWidth={active ? '2.5' : '2'}
        strokeDasharray={active ? '4 3' : undefined}
        className={active ? 'animate-pulse' : ''}
      />
      <polygon
        points="8,18 12,26 16,18"
        fill={active ? '#38bdf8' : completed ? '#10b981' : '#475569'}
      />
    </svg>
  </div>
)

const BranchFork2: React.FC<{
  leftActive?: boolean
  leftCompleted?: boolean
  leftSkipped?: boolean
  rightActive?: boolean
  rightCompleted?: boolean
  rightSkipped?: boolean
}> = ({
  leftActive,
  leftCompleted,
  leftSkipped,
  rightActive,
  rightCompleted,
  rightSkipped,
}) => (
  <div className="w-full flex justify-center my-1 select-none relative" aria-hidden="true">
    <svg width="100%" height="40" viewBox="0 0 280 40" preserveAspectRatio="none" className="overflow-visible">
      {/* Parent Output Port Anchor */}
      <circle cx="140" cy="2" r="3.5" fill="#38bdf8" stroke="#0f172a" strokeWidth="1.5" />

      {/* Left Branch: to draft_plan (70) */}
      <path
        d="M 140 2 C 140 18, 70 18, 70 32"
        fill="none"
        stroke="#334155"
        strokeWidth="2"
      />
      <path
        d="M 140 2 C 140 18, 70 18, 70 32"
        fill="none"
        stroke={leftActive ? '#38bdf8' : leftCompleted ? '#10b981' : leftSkipped ? '#475569' : '#64748b'}
        strokeWidth={leftActive ? '2.5' : '2'}
        strokeDasharray={leftSkipped ? '3 3' : leftActive ? '4 2' : undefined}
        className={leftActive ? 'animate-pulse' : ''}
      />
      <polygon
        points="66,30 70,38 74,30"
        fill={leftActive ? '#38bdf8' : leftCompleted ? '#10b981' : leftSkipped ? '#475569' : '#64748b'}
      />

      {/* Right Branch: to abstain_fallback (210) */}
      <path
        d="M 140 2 C 140 18, 210 18, 210 32"
        fill="none"
        stroke="#334155"
        strokeWidth="2"
      />
      <path
        d="M 140 2 C 140 18, 210 18, 210 32"
        fill="none"
        stroke={rightActive ? '#38bdf8' : rightCompleted ? '#d97706' : rightSkipped ? '#475569' : '#64748b'}
        strokeWidth={rightActive ? '2.5' : '2'}
        strokeDasharray={rightSkipped ? '3 3' : rightActive ? '4 2' : undefined}
        className={rightActive ? 'animate-pulse' : ''}
      />
      <polygon
        points="206,30 210,38 214,30"
        fill={rightActive ? '#38bdf8' : rightCompleted ? '#d97706' : rightSkipped ? '#475569' : '#64748b'}
      />
    </svg>

    {/* Edge Condition Floating Badges */}
    <div className="absolute top-2 w-full flex justify-between px-10 text-[9px] font-mono pointer-events-none">
      <span className="px-1.5 py-0.2 rounded bg-slate-900 border border-slate-700 text-teal-300">
        [chunks &gt; 0]
      </span>
      <span className="px-1.5 py-0.2 rounded bg-slate-900 border border-slate-700 text-amber-300">
        [empty · Rule R2]
      </span>
    </div>
  </div>
)

const BranchJoin2: React.FC<{
  leftCompleted?: boolean
  rightCompleted?: boolean
}> = ({ leftCompleted, rightCompleted }) => (
  <div className="w-full flex justify-center my-1 select-none" aria-hidden="true">
    <svg width="100%" height="32" viewBox="0 0 280 32" preserveAspectRatio="none" className="overflow-visible">
      <path
        d="M 70 2 C 70 16, 140 16, 140 25"
        fill="none"
        stroke={leftCompleted ? '#10b981' : '#334155'}
        strokeWidth="2"
      />
      <path
        d="M 210 2 C 210 16, 140 16, 140 25"
        fill="none"
        stroke={rightCompleted ? '#d97706' : '#334155'}
        strokeWidth="2"
      />
      <polygon
        points="136,23 140,30 144,23"
        fill={leftCompleted || rightCompleted ? '#10b981' : '#64748b'}
      />
    </svg>
  </div>
)

const BranchFork3: React.FC<{
  leftActive?: boolean
  leftCompleted?: boolean
  leftSkipped?: boolean
  midActive?: boolean
  midCompleted?: boolean
  midSkipped?: boolean
  rightActive?: boolean
  rightCompleted?: boolean
  rightSkipped?: boolean
}> = ({
  leftActive,
  leftCompleted,
  leftSkipped,
  midActive,
  midCompleted,
  midSkipped,
  rightActive,
  rightCompleted,
  rightSkipped,
}) => (
  <div className="w-full flex justify-center my-1 select-none relative" aria-hidden="true">
    <svg width="100%" height="46" viewBox="0 0 300 46" preserveAspectRatio="none" className="overflow-visible">
      {/* Anchor point */}
      <circle cx="150" cy="2" r="3.5" fill="#38bdf8" stroke="#0f172a" strokeWidth="1.5" />

      {/* Left Path: block_seal (50) */}
      <path
        d="M 150 2 C 150 22, 50 22, 50 38"
        fill="none"
        stroke="#334155"
        strokeWidth="2"
      />
      <path
        d="M 150 2 C 150 22, 50 22, 50 38"
        fill="none"
        stroke={leftCompleted ? '#f43f5e' : leftActive ? '#38bdf8' : leftSkipped ? '#475569' : '#64748b'}
        strokeWidth={leftActive ? '2.5' : '2'}
        strokeDasharray={leftSkipped ? '3 3' : leftActive ? '4 2' : undefined}
      />
      <polygon
        points="46,36 50,44 54,36"
        fill={leftCompleted ? '#f43f5e' : leftActive ? '#38bdf8' : leftSkipped ? '#475569' : '#64748b'}
      />

      {/* Middle Path: unverified_seal (150) */}
      <line x1="150" y1="2" x2="150" y2="38" stroke="#334155" strokeWidth="2" />
      <line
        x1="150"
        y1="2"
        x2="150"
        y2="38"
        stroke={midCompleted ? '#d97706' : midActive ? '#38bdf8' : midSkipped ? '#475569' : '#64748b'}
        strokeWidth={midActive ? '2.5' : '2'}
        strokeDasharray={midSkipped ? '3 3' : midActive ? '4 2' : undefined}
      />
      <polygon
        points="146,36 150,44 154,36"
        fill={midCompleted ? '#d97706' : midActive ? '#38bdf8' : midSkipped ? '#475569' : '#64748b'}
      />

      {/* Right Path: verified_seal (250) */}
      <path
        d="M 150 2 C 150 22, 250 22, 250 38"
        fill="none"
        stroke="#334155"
        strokeWidth="2"
      />
      <path
        d="M 150 2 C 150 22, 250 22, 250 38"
        fill="none"
        stroke={rightCompleted ? '#10b981' : rightActive ? '#38bdf8' : rightSkipped ? '#475569' : '#64748b'}
        strokeWidth={rightActive ? '2.5' : '2'}
        strokeDasharray={rightSkipped ? '3 3' : rightActive ? '4 2' : undefined}
      />
      <polygon
        points="246,36 250,44 254,36"
        fill={rightCompleted ? '#10b981' : rightActive ? '#38bdf8' : rightSkipped ? '#475569' : '#64748b'}
      />
    </svg>

    {/* Floating Decision Chips */}
    <div className="absolute top-2 w-full flex justify-between px-4 text-[8px] font-mono pointer-events-none">
      <span className="px-1 py-0.2 rounded bg-slate-900 border border-rose-800 text-rose-300">
        [BLOCK · R11]
      </span>
      <span className="px-1 py-0.2 rounded bg-slate-900 border border-amber-800 text-amber-300">
        [Missing · R2]
      </span>
      <span className="px-1 py-0.2 rounded bg-slate-900 border border-emerald-800 text-emerald-300">
        [Clear · R1]
      </span>
    </div>
  </div>
)

const BranchJoin3: React.FC<{
  leftCompleted?: boolean
  midCompleted?: boolean
  rightCompleted?: boolean
}> = ({ leftCompleted, midCompleted, rightCompleted }) => (
  <div className="w-full flex justify-center my-1 select-none" aria-hidden="true">
    <svg width="100%" height="34" viewBox="0 0 300 34" preserveAspectRatio="none" className="overflow-visible">
      <path
        d="M 50 2 C 50 18, 150 18, 150 26"
        fill="none"
        stroke={leftCompleted ? '#f43f5e' : '#334155'}
        strokeWidth="2"
      />
      <line
        x1="150"
        y1="2"
        x2="150"
        y2="26"
        stroke={midCompleted ? '#d97706' : '#334155'}
        strokeWidth="2"
      />
      <path
        d="M 250 2 C 250 18, 150 18, 150 26"
        fill="none"
        stroke={rightCompleted ? '#10b981' : '#334155'}
        strokeWidth="2"
      />
      <polygon
        points="146,24 150,32 154,24"
        fill={
          leftCompleted
            ? '#f43f5e'
            : midCompleted
            ? '#d97706'
            : rightCompleted
            ? '#10b981'
            : '#64748b'
        }
      />
    </svg>
  </div>
)

// ---------------------------------------------------------------------------
// Graph Node Component
// ---------------------------------------------------------------------------

interface GraphNodeCardProps {
  id: string
  label: string
  sublabel?: string
  icon: React.ReactNode
  status: StageStatus
  summary?: string
  accent?: 'default' | 'rose' | 'amber' | 'emerald'
  isCompact?: boolean
  onClick?: () => void
  isSelected?: boolean
}

const GraphNodeCard: React.FC<GraphNodeCardProps> = ({
  id,
  label,
  sublabel,
  icon,
  status,
  summary,
  accent = 'default',
  isCompact = false,
  onClick,
  isSelected = false,
}) => {
  const meta = NODE_CATALOG[id]
  const isRunning = status === 'running'
  const isCompleted = status === 'completed'
  const isSkipped = status === 'skipped'
  const isFailed = status === 'failed'

  let borderStyle = 'border-slate-800 bg-slate-900/90 text-slate-300 hover:border-slate-700'
  let ringStyle = ''
  let portColor = 'bg-slate-600'
  let statusBadge = (
    <span className="text-[10px] text-slate-400 font-medium flex items-center gap-1">
      <Clock className="w-2.5 h-2.5 text-slate-500" />
      Pending
    </span>
  )

  if (isRunning) {
    borderStyle = 'border-cyan-400 bg-cyan-950/70 text-cyan-100 shadow-[0_0_20px_rgba(34,211,238,0.35)]'
    ringStyle = 'ring-1 ring-cyan-400'
    portColor = 'bg-cyan-400 shadow-[0_0_8px_#38bdf8]'
    statusBadge = (
      <span className="text-[10px] text-cyan-300 font-bold flex items-center gap-1">
        <RotateCw className="w-2.5 h-2.5 animate-spin text-cyan-400" />
        Executing
      </span>
    )
  } else if (isCompleted) {
    if (accent === 'rose') {
      borderStyle = 'border-rose-500 bg-rose-950/70 text-rose-100 shadow-[0_0_15px_rgba(244,63,94,0.4)]'
      portColor = 'bg-rose-500 shadow-[0_0_8px_#f43f5e]'
      statusBadge = (
        <span className="text-[10px] text-rose-300 font-bold flex items-center gap-1">
          <AlertOctagon className="w-2.5 h-2.5 text-rose-400" />
          BLOCKED
        </span>
      )
    } else if (accent === 'amber') {
      borderStyle = 'border-amber-500 bg-amber-950/60 text-amber-100 shadow-[0_0_12px_rgba(217,119,6,0.3)]'
      portColor = 'bg-amber-400 shadow-[0_0_8px_#d97706]'
      statusBadge = (
        <span className="text-[10px] text-amber-300 font-bold flex items-center gap-1">
          <HelpCircle className="w-2.5 h-2.5 text-amber-400" />
          UNVERIFIED
        </span>
      )
    } else {
      borderStyle = 'border-emerald-500/80 bg-emerald-950/40 text-emerald-100 shadow-[0_0_12px_rgba(16,185,129,0.2)]'
      portColor = 'bg-emerald-400 shadow-[0_0_8px_#10b981]'
      statusBadge = (
        <span className="text-[10px] text-emerald-300 font-bold flex items-center gap-1">
          <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" />
          Done
        </span>
      )
    }
  } else if (isSkipped) {
    borderStyle = 'border-dashed border-slate-700/80 bg-slate-900/40 text-slate-400 opacity-60'
    portColor = 'bg-slate-700'
    statusBadge = (
      <span className="text-[10px] text-slate-400 font-medium flex items-center gap-1">
        <SkipForward className="w-2.5 h-2.5 text-slate-500" />
        Skipped
      </span>
    )
  } else if (isFailed) {
    borderStyle = 'border-rose-500 bg-rose-950/80 text-rose-200'
    portColor = 'bg-rose-500'
    statusBadge = (
      <span className="text-[10px] text-rose-400 font-bold flex items-center gap-1">
        <XCircle className="w-2.5 h-2.5 text-rose-500" />
        Failed
      </span>
    )
  }

  const selectedRing = isSelected ? 'ring-2 ring-teal-400 ring-offset-2 ring-offset-slate-950' : ''

  return (
    <div
      data-testid={`stage-card-${id}`}
      onClick={onClick}
      className={`relative w-full rounded-xl border backdrop-blur-md transition-all duration-200 cursor-pointer select-none group ${borderStyle} ${ringStyle} ${selectedRing} ${
        isCompact ? 'p-2' : 'p-3'
      }`}
    >
      {/* Top Input Port Socket */}
      <div
        className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full border-2 border-slate-950 flex items-center justify-center z-10 bg-slate-900"
        aria-hidden="true"
      >
        <div className={`w-1.5 h-1.5 rounded-full ${portColor} transition-colors`} />
      </div>

      {/* Micro Stage Header Bar */}
      <div className="flex items-center justify-between gap-1 mb-1.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[8px] font-mono font-bold tracking-widest text-cyan-400 bg-cyan-950/80 px-1.5 py-0.2 rounded border border-cyan-800/60">
            [{meta?.tag || 'NODE'}]
          </span>
          {meta?.rule && !isCompact && (
            <span className="text-[8px] font-mono text-slate-400 bg-slate-800/80 px-1 py-0.2 rounded">
              {meta.rule.split('·')[0].trim()}
            </span>
          )}
        </div>
        <div className="shrink-0">{statusBadge}</div>
      </div>

      {/* Main Node Identity */}
      <div className="flex items-center gap-2">
        <div
          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-xs ${
            isCompleted
              ? accent === 'rose'
                ? 'bg-rose-950 text-rose-300 border border-rose-800'
                : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
              : isRunning
              ? 'bg-cyan-950 text-cyan-300 border border-cyan-500 animate-pulse'
              : 'bg-slate-800 text-slate-400 border border-slate-700'
          }`}
        >
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <h4 className="text-xs font-bold text-slate-100 truncate">
            {label}
          </h4>
          {sublabel && (
            <p className="text-[10px] text-slate-400 truncate leading-none mt-0.5">
              {sublabel}
            </p>
          )}
        </div>
      </div>

      {/* Real-time Safe Summary Feed Line */}
      {summary && (isRunning || isCompleted || isSkipped || isFailed || isSelected) && (
        <div className="mt-2 pt-1.5 border-t border-slate-800/80 flex items-start gap-1 text-[10px] font-mono text-cyan-200/90 leading-tight">
          <span className="text-teal-400 font-bold shrink-0">›</span>
          <span className="break-words">{summary}</span>
        </div>
      )}

      {/* Bottom Output Port Socket */}
      <div
        className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full border-2 border-slate-950 flex items-center justify-center z-10 bg-slate-900"
        aria-hidden="true"
      >
        <div className={`w-1.5 h-1.5 rounded-full ${portColor} transition-colors`} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main LiveProcessPanel Component
// ---------------------------------------------------------------------------

interface LiveProcessPanelProps {
  events: TriageLifecycleEvent[]
  isLoading: boolean
  className?: string
  onNavigateToReport?: () => void
}

export const LiveProcessPanel: React.FC<LiveProcessPanelProps> = ({
  events,
  isLoading,
  className = '',
  onNavigateToReport,
}) => {
  const [activeTab, setActiveTab] = useState<'graph' | 'feed'>('graph')
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const feedEndRef = useRef<HTMLDivElement>(null)

  const isRunComplete = useMemo(() => {
    return events.some((e) => e.event_type === 'run.completed')
  }, [events])

  // Derive individual node execution states directly from emitted SSE events
  const nodeStates = useMemo(() => {
    const states: Record<string, { status: StageStatus; summary: string; timestamp?: string }> = {
      validation: { status: 'pending', summary: '' },
      normalise: { status: 'pending', summary: '' },
      intake_safety_checks: { status: 'pending', summary: '' },
      retrieve: { status: 'pending', summary: '' },
      draft_plan: { status: 'pending', summary: '' },
      abstain_fallback: { status: 'pending', summary: '' },
      verify: { status: 'pending', summary: '' },
      block_seal: { status: 'pending', summary: '' },
      unverified_seal: { status: 'pending', summary: '' },
      verified_seal: { status: 'pending', summary: '' },
      audit: { status: 'pending', summary: '' },
      explain: { status: 'pending', summary: '' },
    }

    for (const ev of events) {
      if (states[ev.stage]) {
        if (ev.event_type === 'stage.started') {
          states[ev.stage] = {
            status: 'running',
            summary: ev.safe_summary,
            timestamp: ev.timestamp,
          }
        } else if (ev.event_type === 'stage.completed') {
          states[ev.stage] = {
            status: 'completed',
            summary: ev.safe_summary,
            timestamp: ev.timestamp,
          }
        } else if (ev.event_type === 'stage.skipped') {
          states[ev.stage] = {
            status: 'skipped',
            summary: ev.safe_summary,
            timestamp: ev.timestamp,
          }
        } else if (ev.event_type === 'stage.failed') {
          states[ev.stage] = {
            status: 'failed',
            summary: ev.safe_summary,
            timestamp: ev.timestamp,
          }
        }
      }
    }

    return states
  }, [events])

  // Count sealed stages
  const completedCount = useMemo(() => {
    return Object.values(nodeStates).filter((s) => s.status === 'completed').length
  }, [nodeStates])

  // Auto-scroll activity feed to latest event
  useEffect(() => {
    if (
      activeTab === 'feed' &&
      feedEndRef.current &&
      typeof feedEndRef.current.scrollIntoView === 'function'
    ) {
      feedEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events, activeTab])

  const formatTime = (isoString?: string) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      const base = d.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
      const ms = String(d.getMilliseconds()).padStart(3, '0')
      return `${base}.${ms}`
    } catch {
      return ''
    }
  }

  const selectedNodeMeta = selectedNode ? NODE_CATALOG[selectedNode] : null
  const selectedNodeState = selectedNode ? nodeStates[selectedNode] : null

  return (
    <div
      data-testid="live-process-panel"
      className={`flex flex-col rounded-3xl border border-slate-800 bg-slate-950 text-slate-100 shadow-2xl overflow-hidden ${className}`}
    >
      {/* Workbench Header Bar */}
      <div className="flex flex-col gap-2 p-4 sm:p-5 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-cyan-950 text-cyan-400 border border-cyan-800/80 shadow-[0_0_12px_rgba(34,211,238,0.2)]">
              <Workflow className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                  LangGraph State Machine Process Graph
                </h3>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-cyan-300 border border-slate-700">
                  DAG Engine
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Deterministic Directed Graph · Rule R1 &amp; Rule R2
              </p>
            </div>
          </div>

          {/* Mode Badge */}
          <div className="flex items-center gap-2">
            {isLoading ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-cyan-950 text-cyan-300 border border-cyan-500 shadow-[0_0_12px_rgba(34,211,238,0.4)]">
                <span className="h-2 w-2 rounded-full bg-cyan-400 animate-ping" />
                Active Run
              </span>
            ) : isRunComplete ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-950 text-emerald-300 border border-emerald-600 shadow-[0_0_12px_rgba(16,185,129,0.3)]">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                Finished
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-900 text-slate-400 border border-slate-700">
                Standby
              </span>
            )}
          </div>
        </div>

        {/* View Switcher & Topology Metrics */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center bg-slate-900 p-0.5 rounded-xl border border-slate-800 text-xs font-medium">
            <button
              type="button"
              onClick={() => setActiveTab('graph')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-colors ${
                activeTab === 'graph'
                  ? 'bg-slate-800 text-white shadow-soft-sm font-semibold border border-slate-700'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Workflow className="w-3.5 h-3.5 text-cyan-400" />
              Process Graph
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('feed')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-colors ${
                activeTab === 'feed'
                  ? 'bg-slate-800 text-white shadow-soft-sm font-semibold border border-slate-700'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Terminal className="w-3.5 h-3.5 text-teal-400" />
              Activity Feed ({events.length})
            </button>
          </div>

          <div className="text-right text-[11px] text-slate-400 font-mono">
            <span className="font-semibold text-emerald-400">
              {completedCount} of 11
            </span>{' '}
            nodes sealed
          </div>
        </div>
      </div>

      {/* Main Graph Canvas Area */}
      <div className="flex-1 p-3.5 sm:p-5 overflow-y-auto max-h-[620px] relative bg-slate-950">
        {activeTab === 'graph' ? (
          <div className="relative">
            {/* Visual Dot Grid Canvas Texture */}
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none opacity-20"
              aria-hidden="true"
            >
              <defs>
                <pattern id="dag-dot-grid" width="22" height="22" patternUnits="userSpaceOnUse">
                  <circle cx="2" cy="2" r="1.2" fill="#38bdf8" />
                  <circle cx="13" cy="13" r="0.8" fill="#475569" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#dag-dot-grid)" />
            </svg>

            {/* Visual Topology Legend Bar */}
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 p-2 rounded-xl bg-slate-900/80 border border-slate-800 text-[10px] font-mono text-slate-400">
              <span className="flex items-center gap-1 text-slate-300">
                <Cpu className="w-3 h-3 text-cyan-400" />
                DAG Topology: 11 Nodes · 12 Edges · 2 Dynamic Routers
              </span>
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_6px_#38bdf8]" />
                  Active
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#10b981]" />
                  Done
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-rose-400 shadow-[0_0_6px_#f43f5e]" />
                  Blocked
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-slate-600 border border-dashed border-slate-500" />
                  Skipped
                </span>
              </div>
            </div>

            {/* Directed Graph Vertical Track */}
            <div className="flex flex-col items-center max-w-md mx-auto relative z-10">
              {/* 1. Request Validation */}
              <GraphNodeCard
                id="validation"
                label="1. Request Validation"
                sublabel="Pydantic Clinical Ingress Schema Gate"
                icon={<FileCheck className="w-3.5 h-3.5" />}
                status={nodeStates.validation.status}
                summary={nodeStates.validation.summary}
                onClick={() => setSelectedNode('validation')}
                isSelected={selectedNode === 'validation'}
              />

              {/* Edge 1 -> 2 */}
              <VerticalEdge
                active={nodeStates.normalise.status === 'running'}
                completed={nodeStates.normalise.status === 'completed'}
              />

              {/* 2. Normalisation & Early Warning Score */}
              <GraphNodeCard
                id="normalise"
                label="2. Normalisation & EWS"
                sublabel="Vital Observations & Score Band Calculation"
                icon={<Scale className="w-3.5 h-3.5" />}
                status={nodeStates.normalise.status}
                summary={nodeStates.normalise.summary}
                onClick={() => setSelectedNode('normalise')}
                isSelected={selectedNode === 'normalise'}
              />

              {/* Edge 2 -> 3 */}
              <VerticalEdge
                active={nodeStates.intake_safety_checks.status === 'running'}
                completed={nodeStates.intake_safety_checks.status === 'completed'}
              />

              {/* 3. Baseline Safety Checks */}
              <GraphNodeCard
                id="intake_safety_checks"
                label="3. Baseline Safety Interlocks"
                sublabel="Pass 1 Allergies, DDIs, Formulary Limits"
                icon={<ShieldAlert className="w-3.5 h-3.5" />}
                status={nodeStates.intake_safety_checks.status}
                summary={nodeStates.intake_safety_checks.summary}
                onClick={() => setSelectedNode('intake_safety_checks')}
                isSelected={selectedNode === 'intake_safety_checks'}
              />

              {/* Edge 3 -> 4 */}
              <VerticalEdge
                active={nodeStates.retrieve.status === 'running'}
                completed={nodeStates.retrieve.status === 'completed'}
              />

              {/* 4. Protocol Retrieval */}
              <GraphNodeCard
                id="retrieve"
                label="4. Protocol Retrieval"
                sublabel="BM25 Lexical &amp; Vitals-Flag Guidance"
                icon={<BookOpen className="w-3.5 h-3.5" />}
                status={nodeStates.retrieve.status}
                summary={nodeStates.retrieve.summary}
                onClick={() => setSelectedNode('retrieve')}
                isSelected={selectedNode === 'retrieve'}
              />

              {/* CONDITIONAL FORK 1: Retrieval Decision Router */}
              <BranchFork2
                leftActive={nodeStates.draft_plan.status === 'running'}
                leftCompleted={nodeStates.draft_plan.status === 'completed'}
                leftSkipped={nodeStates.draft_plan.status === 'skipped'}
                rightActive={nodeStates.abstain_fallback.status === 'running'}
                rightCompleted={nodeStates.abstain_fallback.status === 'completed'}
                rightSkipped={nodeStates.abstain_fallback.status === 'skipped'}
              />

              {/* Level 5: 2 Branches (Draft Plan vs Fail-Closed Fallback) */}
              <div className="grid grid-cols-2 gap-3 w-full">
                <GraphNodeCard
                  id="draft_plan"
                  label="5a. Plan Drafting"
                  sublabel="Extractive Synthesis"
                  icon={<FileText className="w-3.5 h-3.5" />}
                  status={nodeStates.draft_plan.status}
                  summary={nodeStates.draft_plan.summary}
                  isCompact
                  onClick={() => setSelectedNode('draft_plan')}
                  isSelected={selectedNode === 'draft_plan'}
                />
                <GraphNodeCard
                  id="abstain_fallback"
                  label="5b. Abstain Fallback"
                  sublabel="Fail-Closed (Rule R2)"
                  icon={<Filter className="w-3.5 h-3.5" />}
                  status={nodeStates.abstain_fallback.status}
                  summary={nodeStates.abstain_fallback.summary}
                  accent="amber"
                  isCompact
                  onClick={() => setSelectedNode('abstain_fallback')}
                  isSelected={selectedNode === 'abstain_fallback'}
                />
              </div>

              {/* CONDITIONAL JOIN 1: Converge into Machine Verification */}
              <BranchJoin2
                leftCompleted={nodeStates.draft_plan.status === 'completed'}
                rightCompleted={nodeStates.abstain_fallback.status === 'completed'}
              />

              {/* 6. Machine Verification */}
              <GraphNodeCard
                id="verify"
                label="6. Machine Verification"
                sublabel="Pass 2 Deterministic Verifier &amp; Dose Math"
                icon={<ShieldCheck className="w-3.5 h-3.5" />}
                status={nodeStates.verify.status}
                summary={nodeStates.verify.summary}
                onClick={() => setSelectedNode('verify')}
                isSelected={selectedNode === 'verify'}
              />

              {/* CONDITIONAL FORK 2: Verdict Lattice Resolution (3 Branches) */}
              <BranchFork3
                leftActive={nodeStates.block_seal.status === 'running'}
                leftCompleted={nodeStates.block_seal.status === 'completed'}
                leftSkipped={nodeStates.block_seal.status === 'skipped'}
                midActive={nodeStates.unverified_seal.status === 'running'}
                midCompleted={nodeStates.unverified_seal.status === 'completed'}
                midSkipped={nodeStates.unverified_seal.status === 'skipped'}
                rightActive={nodeStates.verified_seal.status === 'running'}
                rightCompleted={nodeStates.verified_seal.status === 'completed'}
                rightSkipped={nodeStates.verified_seal.status === 'skipped'}
              />

              {/* Level 7: 3 Verdict Branches */}
              <div className="grid grid-cols-3 gap-2 w-full">
                <GraphNodeCard
                  id="block_seal"
                  label="BLOCK Seal"
                  sublabel="Rule R11 Interlock"
                  icon={<AlertOctagon className="w-3 h-3" />}
                  status={nodeStates.block_seal.status}
                  summary={nodeStates.block_seal.summary}
                  accent="rose"
                  isCompact
                  onClick={() => setSelectedNode('block_seal')}
                  isSelected={selectedNode === 'block_seal'}
                />
                <GraphNodeCard
                  id="unverified_seal"
                  label="UNVERIFIED"
                  sublabel="Rule R2 Boundary"
                  icon={<HelpCircle className="w-3 h-3" />}
                  status={nodeStates.unverified_seal.status}
                  summary={nodeStates.unverified_seal.summary}
                  accent="amber"
                  isCompact
                  onClick={() => setSelectedNode('unverified_seal')}
                  isSelected={selectedNode === 'unverified_seal'}
                />
                <GraphNodeCard
                  id="verified_seal"
                  label="VERIFIED"
                  sublabel="Authorized Care"
                  icon={<CheckCircle2 className="w-3 h-3" />}
                  status={nodeStates.verified_seal.status}
                  summary={nodeStates.verified_seal.summary}
                  accent="emerald"
                  isCompact
                  onClick={() => setSelectedNode('verified_seal')}
                  isSelected={selectedNode === 'verified_seal'}
                />
              </div>

              {/* CONDITIONAL JOIN 2: Converge into Cryptographic Audit */}
              <BranchJoin3
                leftCompleted={nodeStates.block_seal.status === 'completed'}
                midCompleted={nodeStates.unverified_seal.status === 'completed'}
                rightCompleted={nodeStates.verified_seal.status === 'completed'}
              />

              {/* 8. Cryptographic Audit */}
              <GraphNodeCard
                id="audit"
                label="8. Cryptographic Audit"
                sublabel="SHA-256 Tamper-Evident Hash Chain"
                icon={<Lock className="w-3.5 h-3.5" />}
                status={nodeStates.audit.status}
                summary={nodeStates.audit.summary}
                onClick={() => setSelectedNode('audit')}
                isSelected={selectedNode === 'audit'}
              />

              {/* Edge 8 -> 9 */}
              <VerticalEdge
                active={nodeStates.explain.status === 'running'}
                completed={nodeStates.explain.status === 'completed'}
              />

              {/* 9. Report Assembly */}
              <GraphNodeCard
                id="explain"
                label="9. Report Assembly"
                sublabel="EngineReport &amp; Clinical Action Plan"
                icon={<FileCheck className="w-3.5 h-3.5" />}
                status={nodeStates.explain.status}
                summary={nodeStates.explain.summary}
                onClick={() => setSelectedNode('explain')}
                isSelected={selectedNode === 'explain'}
              />
            </div>

            {/* Interactive Node Telemetry Drawer */}
            {selectedNode && selectedNodeMeta && (
              <div className="mt-4 p-4 rounded-2xl border border-cyan-800 bg-slate-900/95 backdrop-blur-md shadow-2xl animate-fade-in relative">
                <button
                  type="button"
                  onClick={() => setSelectedNode(null)}
                  className="absolute top-3 right-3 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
                  aria-label="Close details"
                >
                  <X className="w-4 h-4" />
                </button>

                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[9px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                    STAGE {selectedNodeMeta.index}
                  </span>
                  <span className="text-xs font-bold text-white">
                    {selectedNodeMeta.rule}
                  </span>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed mb-3">
                  {selectedNodeMeta.description}
                </p>

                <div className="rounded-xl border border-slate-800 bg-slate-950 p-2.5 space-y-1.5 text-[11px] font-mono">
                  <div className="flex items-center justify-between text-slate-400">
                    <span>LangGraph Invariant:</span>
                    <span className="text-teal-300">{selectedNodeMeta.ruleRef}</span>
                  </div>
                  <p className="text-slate-300 text-[10px] leading-tight">
                    {selectedNodeMeta.invariant}
                  </p>
                  {selectedNodeState?.summary && (
                    <div className="pt-1.5 border-t border-slate-800/80 text-cyan-300 text-[10px]">
                      <span className="text-slate-500">Live Telemetry: </span>
                      {selectedNodeState.summary}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Real-Time Activity Feed Tab */
          <div className="space-y-2">
            {events.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 px-4 text-center text-slate-500">
                <Terminal className="h-8 w-8 mb-2 stroke-1 text-slate-600" />
                <p className="text-xs font-medium text-slate-300">No live events emitted yet.</p>
                <p className="text-[11px] mt-1 max-w-xs text-slate-400">
                  Submit patient details to stream real execution events directly from the LangGraph engine.
                </p>
              </div>
            ) : (
              events.map((ev, i) => (
                <div
                  key={`${ev.request_id}-${ev.sequence}-${i}`}
                  data-testid="feed-event-item"
                  className="flex items-start gap-2.5 p-2.5 rounded-xl border border-slate-800 bg-slate-900/60 text-xs font-mono"
                >
                  <span className="text-[10px] font-bold text-cyan-400 px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700">
                    #{String(ev.sequence).padStart(2, '0')}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span
                        className={`text-[10px] uppercase font-bold px-1.5 py-0.2 rounded ${
                          ev.event_type === 'stage.completed' || ev.event_type === 'run.completed'
                            ? 'text-emerald-300 bg-emerald-950 border border-emerald-800'
                            : ev.event_type === 'stage.started'
                            ? 'text-cyan-300 bg-cyan-950 border border-cyan-800'
                            : ev.event_type === 'stage.skipped'
                            ? 'text-amber-300 bg-amber-950 border border-amber-800'
                            : 'text-rose-300 bg-rose-950 border border-rose-800'
                        }`}
                      >
                        {ev.stage}
                      </span>
                      <span className="text-[10px] text-slate-400">{formatTime(ev.timestamp)}</span>
                    </div>
                    <p className="text-[11px] text-slate-200 mt-1 break-words">
                      {ev.safe_summary}
                    </p>
                  </div>
                </div>
              ))
            )}
            <div ref={feedEndRef} />
          </div>
        )}
      </div>

      {/* Academic Safety / Disclaimer Footer */}
      <div className="p-3 border-t border-slate-800 bg-slate-900/90 flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-left">
        <p className="text-[10px] text-slate-400 font-mono">
          Academic Observability Only. Driven by LangGraph State Machine. Not a clinical device.
        </p>
        {onNavigateToReport && isRunComplete && !isLoading && (
          <button
            type="button"
            onClick={onNavigateToReport}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-teal-600 hover:bg-teal-500 shadow-[0_0_12px_rgba(20,184,166,0.4)] transition-all shrink-0 cursor-pointer"
          >
            <span>Proceed to Results</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        )}
      </div>
    </div>
  )
}

export default LiveProcessPanel
