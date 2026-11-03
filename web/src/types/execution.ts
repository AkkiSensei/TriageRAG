/**
 * Strongly-typed definitions for the live process graph and real-time activity feed (ADR 0017).
 *
 * Safety Properties (Rule R1, Rule R2, Rule R7):
 * 1. Strictly maps backend lifecycle events into user-readable execution stages.
 * 2. Zero artificial timers; stage statuses update exclusively upon real backend SSE messages.
 * 3. Privacy allowlist: safe summaries contain zero PII, raw vitals, or medication names.
 */

export type TriageLifecycleEventType =
  | 'stage.started'
  | 'stage.completed'
  | 'stage.skipped'
  | 'stage.failed'
  | 'run.completed'

export type StageStatus = 'pending' | 'running' | 'completed' | 'skipped' | 'failed'

export interface TriageLifecycleEvent {
  request_id: string
  sequence: number
  timestamp: string
  event_type: TriageLifecycleEventType
  stage: string
  status: StageStatus
  safe_summary: string
  data?: Record<string, unknown> | null
}

export interface ProcessStageDefinition {
  id: string
  backendStages: string[]
  label: string
  shortLabel: string
  description: string
  category: 'intake' | 'retrieval' | 'verification' | 'disposition'
}

export const PROCESS_STAGES: ProcessStageDefinition[] = [
  {
    id: 'validation',
    backendStages: ['validation'],
    label: '1. Request Validation',
    shortLabel: 'Validation',
    description: 'Strict schema and type checking on incoming synthetic patient record',
    category: 'intake',
  },
  {
    id: 'normalise',
    backendStages: ['normalise'],
    label: '2. Normalisation & Scoring',
    shortLabel: 'Normalise',
    description: 'Observation normalisation and deterministic early warning scoring',
    category: 'intake',
  },
  {
    id: 'intake_safety_checks',
    backendStages: ['intake_safety_checks'],
    label: '3. Baseline Safety Checks',
    shortLabel: 'Safety Checks',
    description: 'Pass 1 deterministic rules (Allergies, DDIs, Formulary contraindications)',
    category: 'intake',
  },
  {
    id: 'retrieve',
    backendStages: ['retrieve'],
    label: '4. Evidence Retrieval',
    shortLabel: 'Retrieval',
    description: 'Protocol evidence retrieval and calibrated abstention scoring',
    category: 'retrieval',
  },
  {
    id: 'draft_plan',
    backendStages: ['draft_plan', 'abstain_fallback'],
    label: '5. Plan Drafting / Fallback',
    shortLabel: 'Plan Drafting',
    description: 'Extractive protocol action drafting (or fail-closed fallback if abstained)',
    category: 'retrieval',
  },
  {
    id: 'verify',
    backendStages: ['verify'],
    label: '6. Machine Verification',
    shortLabel: 'Verification',
    description: 'Pass 2 deterministic verification, dose checks, and verdict lattice',
    category: 'verification',
  },
  {
    id: 'disposition_seal',
    backendStages: ['block_seal', 'unverified_seal', 'verified_seal'],
    label: '7. Disposition Seal',
    shortLabel: 'Seal',
    description: 'Cryptographic sealing under BLOCK (R11), UNVERIFIED (R2), or VERIFIED',
    category: 'disposition',
  },
  {
    id: 'audit',
    backendStages: ['audit'],
    label: '8. Cryptographic Audit',
    shortLabel: 'Audit',
    description: 'SHA-256 tamper-evident cryptographic hash-chain logging',
    category: 'disposition',
  },
  {
    id: 'explain',
    backendStages: ['explain'],
    label: '9. Report Assembly',
    shortLabel: 'Assembly',
    description: 'Final EngineReport, ActionPlan derivation, and confidence packaging',
    category: 'disposition',
  },
]
