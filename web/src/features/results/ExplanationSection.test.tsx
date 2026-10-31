import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ExplanationSection } from './ExplanationSection'
import type { TriageResponse } from '@/lib/api'

const createMockTriage = (overrides?: Partial<TriageResponse>): TriageResponse => {
  return {
    engine: {
      verdict: 'CHECKED_CLEAR',
      checks_run: 15,
      checks_skipped: [],
      unresolved_entities: [],
      ruleset_coverage: ['15 rules evaluated'],
      coverage_gaps: ['Renal impairment'],
      baseline_alerts: [],
      plan_alerts: [],
      score: {
        score_name: 'NEWS2',
        total_score: 2,
        band: 'GREEN',
        missing_vitals: [],
      },
    },
    verified_steps: [
      {
        draft: {
          step_number: 1,
          action_type: 'administer',
          drug_id: 'epinephrine',
          narrative_instruction: 'Administer epinephrine 0.5 mg IM',
        },
        status: 'APPROVED',
        triggered_rule_ids: [],
        rejection_reasons: [],
        citation_verified: true,
      },
    ],
    retrieval: {
      chunks: [
        {
          chunk_id: 'CHUNK_01',
          doc_id: 'DOC_SYNTH_01',
          section: 'Management',
          text: 'Administer epinephrine promptly.',
        },
      ],
      backend: 'bm25',
      abstained: false,
      abstain_code: 'NONE',
      reason: null,
      filters: { population: 'adult', syndrome: 'anaphylaxis' },
    },
    explanation: {
      headline: 'CHECKED CLEAR: No Configured Safety Rules Triggered',
      plain_language_summary: 'All applicable deterministic rules fired clear.',
      outcome_reasons: ['No active alerts, blocked steps, or abstentions were recorded.'],
      retrieval_explanation: 'Successfully retrieved 1 protocol chunk.',
      evidence_summary: 'Top retrieved evidence: Document DOC_SYNTH_01.',
      completed_checks: [
        'Evaluated 15 registered safety rules across formulary and ontology',
        'Allergy and cross-reactivity interlock evaluation',
        'Deterministic contraindication and drug-drug interaction screening',
        'Machine-verified 1 proposed protocol steps against retrieved evidence and formulary limits',
      ],
      unresolved_checks: ['Known ruleset coverage gap: Renal impairment'],
      generation_disclosure: 'Plan generation mode: deterministic_mock.',
      permitted_ui_actions: ['Review verified protocol steps with senior clinical staff.'],
    },
    llm_fallback_mode: false,
    audit_hash: 'abc123456789',
    ...overrides,
  } as TriageResponse
}

describe('ExplanationSection Component Tests', () => {
  it('renders headline and plain language summary correctly', () => {
    const mock = createMockTriage()
    render(<ExplanationSection triage={mock} />)

    expect(screen.getByText(/CHECKED CLEAR: No Configured Safety Rules Triggered/i)).toBeInTheDocument()
    expect(screen.getByText(/All applicable deterministic rules fired clear/i)).toBeInTheDocument()
  })

  it('renders UNVERIFIED verdict and displays retrieval abstention code', () => {
    const mock = createMockTriage({
      engine: {
        verdict: 'UNVERIFIED',
        checks_run: 5,
        checks_skipped: [],
        unresolved_entities: [],
        ruleset_coverage: [],
        coverage_gaps: [],
        baseline_alerts: [],
        plan_alerts: [],
      },
      retrieval: {
        chunks: [],
        backend: 'bm25',
        abstained: true,
        abstain_code: 'NO_POPULATION_COVERAGE',
        reason: 'No protocol coverage for neonatal',
      },
      explanation: {
        headline: 'UNVERIFIED: Protocol Retrieval Abstained (NO_POPULATION_COVERAGE)',
        plain_language_summary: 'The system could not establish a verified clinical plan.',
        outcome_reasons: ['[RETRIEVAL ABSTAINED] Protocol retrieval did not proceed'],
        retrieval_explanation: 'Retrieval abstained under safety gate NO_POPULATION_COVERAGE',
        evidence_summary: 'No protocol evidence chunks were retrieved.',
        completed_checks: ['Evaluated 5 registered safety rules'],
        unresolved_checks: ['Protocol retrieval abstained (NO_POPULATION_COVERAGE)'],
        generation_disclosure: 'Deterministic mock mode.',
        permitted_ui_actions: ['Provide missing patient data.'],
      },
    })

    render(<ExplanationSection triage={mock} />)

    expect(screen.getAllByText(/UNVERIFIED/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/NO_POPULATION_COVERAGE/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/The system could not establish a verified clinical plan/i)).toBeInTheDocument()
  })

  it('renders BLOCKED verdict styling and badge', () => {
    const mock = createMockTriage({
      engine: {
        verdict: 'BLOCKED',
        checks_run: 10,
        checks_skipped: [],
        unresolved_entities: [],
        ruleset_coverage: [],
        coverage_gaps: [],
        baseline_alerts: [],
        plan_alerts: [],
      },
      explanation: {
        headline: 'BLOCKED: Absolute Safety Interlock Triggered',
        plain_language_summary: 'A deterministic safety rule blocked this proposal.',
        outcome_reasons: ['[BLOCK] Absolute contraindication triggered.'],
        retrieval_explanation: 'Retrieval completed.',
        evidence_summary: 'Evidence available.',
        completed_checks: [],
        unresolved_checks: [],
        generation_disclosure: 'Deterministic mock mode.',
        permitted_ui_actions: ['Review contraindicated medication.'],
      },
    })

    render(<ExplanationSection triage={mock} />)
    expect(screen.getAllByText(/BLOCKED/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/Absolute Safety Interlock Triggered/i)).toBeInTheDocument()
  })

  it('renders CHECKED WITH ALERTS verdict styling', () => {
    const mock = createMockTriage({
      engine: {
        verdict: 'CHECKED_ALERTS',
        checks_run: 12,
        checks_skipped: [],
        unresolved_entities: [],
        ruleset_coverage: [],
        coverage_gaps: [],
        baseline_alerts: [],
        plan_alerts: [],
      },
      explanation: {
        headline: 'CHECKED WITH ALERTS: Clinical Warnings Require Review',
        plain_language_summary: 'Deterministic safety checks identified non-blocking warnings.',
        outcome_reasons: ['[HIGH] Potential duplicate therapy.'],
        retrieval_explanation: 'Retrieval completed.',
        evidence_summary: 'Evidence available.',
        completed_checks: [],
        unresolved_checks: [],
        generation_disclosure: 'Deterministic mock mode.',
        permitted_ui_actions: ['Review non-blocking alerts.'],
      },
    })

    render(<ExplanationSection triage={mock} />)
    expect(screen.getAllByText(/CHECKED WITH ALERTS/i).length).toBeGreaterThan(0)
  })

  it('never displays bare word CLEAR in non-clear verdicts', () => {
    const mock = createMockTriage({
      engine: {
        verdict: 'UNVERIFIED',
        checks_run: 5,
        checks_skipped: [],
        unresolved_entities: [],
        ruleset_coverage: [],
        coverage_gaps: [],
        baseline_alerts: [],
        plan_alerts: [],
      },
    })

    const { container } = render(<ExplanationSection triage={mock} />)
    const text = container.textContent || ''
    // If "CLEAR" appears, it must NOT be bare or indicate clearance
    const bareClear = /\bCLEAR\b/.test(text.replace(/CHECKED CLEAR/g, ''))
    expect(bareClear).toBe(false)
  })

  it('displays completed checks items from actual execution', () => {
    const mock = createMockTriage()
    render(<ExplanationSection triage={mock} />)

    expect(screen.getByText(/Allergy and cross-reactivity interlock evaluation/i)).toBeInTheDocument()
    expect(screen.getByText(/Deterministic contraindication and drug-drug interaction/i)).toBeInTheDocument()
  })

  it('displays unresolved checks and coverage gaps', () => {
    const mock = createMockTriage()
    render(<ExplanationSection triage={mock} />)

    expect(screen.getByText(/Known ruleset coverage gap: Renal impairment/i)).toBeInTheDocument()
  })

  it('toggles execution timeline drawer when button is clicked', () => {
    const mock = createMockTriage()
    render(<ExplanationSection triage={mock} />)

    const toggleButton = screen.getByRole('button', { name: /Execution Pipeline Timeline/i })
    expect(toggleButton).toBeInTheDocument()

    // Initially timeline is collapsed
    expect(screen.queryByText(/4\. Deterministic Safety Interlocks/i)).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(toggleButton)
    expect(screen.getByText(/4\. Deterministic Safety Interlocks/i)).toBeInTheDocument()
  })

  it('timeline reflects UNRESOLVED ENTITIES when entities exist', () => {
    const mock = createMockTriage({
      engine: {
        verdict: 'UNVERIFIED',
        checks_run: 5,
        checks_skipped: [],
        unresolved_entities: ['Metformin XR', 'Lisinopril 10mg'],
        ruleset_coverage: [],
        coverage_gaps: [],
        baseline_alerts: [],
        plan_alerts: [],
      },
    })

    render(<ExplanationSection triage={mock} />)
    fireEvent.click(screen.getByRole('button', { name: /Execution Pipeline Timeline/i }))

    expect(screen.getByText(/UNRESOLVED ENTITIES/i)).toBeInTheDocument()
    expect(screen.getByText(/2 unmapped entities/i)).toBeInTheDocument()
  })

  it('renders generation disclosure emphasizing deterministic mock mode', () => {
    const mock = createMockTriage()
    render(<ExplanationSection triage={mock} />)

    expect(screen.getByText(/Plan generation mode: deterministic_mock/i)).toBeInTheDocument()
  })
})
