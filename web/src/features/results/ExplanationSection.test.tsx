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

  it('renders rejected paths explaining why alternative paths were rejected', () => {
    const mock = createMockTriage({
      explanation: {
        headline: 'BLOCKED: Absolute Safety Interlock Triggered',
        plain_language_summary: 'Contraindication interlock fired.',
        outcome_reasons: ['[BLOCK] Absolute contraindication triggered.'],
        retrieval_explanation: 'Retrieval completed.',
        evidence_summary: 'Evidence available.',
        completed_checks: [],
        unresolved_checks: [],
        rejected_paths: [
          'Rejected CHECKED_CLEAR: Rule R11 strictly prohibits clearing a plan when a BLOCK severity alert is active.',
          'Rejected CHECKED_ALERTS: Absolute contraindication interlocks cannot be overridden by clinical judgment.',
        ],
        generation_disclosure: 'Deterministic mock mode.',
        permitted_ui_actions: [],
      },
    })
    render(<ExplanationSection triage={mock} />)

    expect(screen.getByText(/Why Alternative Paths Were Rejected/i)).toBeInTheDocument()
    expect(screen.getByText(/Rejected CHECKED_CLEAR: Rule R11 strictly prohibits/i)).toBeInTheDocument()
    expect(screen.getByText(/Rejected CHECKED_ALERTS: Absolute contraindication/i)).toBeInTheDocument()
  })

  it('toggles input normalization ledger drawer', () => {
    const mock = createMockTriage({
      patient: {
        medications: [
          { raw_text: 'Advil 200mg', resolved: true, ingredients: [{ ingredient_id: 'ibuprofen' }] },
          { raw_text: 'UnknownHerb', resolved: false, suggestion: 'St Johns Wort' },
        ],
        allergies: [
          { raw_substance: 'Penicillin', resolved: true, normalized_allergen_id: 'penicillin' },
        ],
        age: { value: '45', unit: 'years' },
      } as unknown as NonNullable<TriageResponse['patient']>,
    })
    render(<ExplanationSection triage={mock} />)

    const toggleButton = screen.getByRole('button', { name: /Input Normalization Ledger/i })
    expect(toggleButton).toBeInTheDocument()

    // Initially collapsed
    expect(screen.queryByText(/Medications Normalization/i)).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(toggleButton)
    expect(screen.getByText(/Medications Normalization/i)).toBeInTheDocument()
    expect(screen.getByText(/Advil 200mg/i)).toBeInTheDocument()
    expect(screen.getByText(/ibuprofen/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Penicillin/i).length).toBeGreaterThan(0)
  })

  it('toggles retriever evidence and plan grounding ledger', () => {
    const mock = createMockTriage()
    render(<ExplanationSection triage={mock} />)

    const toggleButton = screen.getByRole('button', { name: /Retriever Evidence & Plan Grounding Ledger/i })
    expect(toggleButton).toBeInTheDocument()

    // Initially collapsed
    expect(screen.queryByText(/Retrieved Protocol Evidence Chunks/i)).not.toBeInTheDocument()

    // Click to expand
    fireEvent.click(toggleButton)
    expect(screen.getByText(/Retrieved Protocol Evidence Chunks/i)).toBeInTheDocument()
    expect(screen.getByText(/CHUNK_01/i)).toBeInTheDocument()
  })

  it('renders live LangGraph execution trace nodes when execution_trace is provided', () => {
    const mock = createMockTriage({
      execution_trace: [
        { node: 'normalise', status: 'completed', duration_ms: 1.25, details: {} },
        { node: 'intake_safety', status: 'completed', duration_ms: 3.42, details: {} },
        { node: 'retrieve', status: 'completed', duration_ms: 2.10, details: {} },
        { node: 'draft_plan', status: 'completed', duration_ms: 5.60, details: {} },
        { node: 'verify_plan', status: 'completed', duration_ms: 4.80, details: {} },
        { node: 'block_seal', status: 'completed', duration_ms: 0.35, details: {} },
        { node: 'audit', status: 'completed', duration_ms: 1.15, details: {} },
        { node: 'explain', status: 'completed', duration_ms: 2.05, details: {} },
      ],
    } as unknown as Partial<TriageResponse>)
    render(<ExplanationSection triage={mock} />)

    fireEvent.click(screen.getByRole('button', { name: /Execution Pipeline Timeline/i }))
    expect(screen.getByText(/Live LangGraph Runtime State Nodes/i)).toBeInTheDocument()
    expect(screen.getByText(/1\. normalise/i)).toBeInTheDocument()
    expect(screen.getByText(/1\.25 ms/i)).toBeInTheDocument()
  })

  it('renders clinical action plan with immediate actions and medications when present', () => {
    const mock = createMockTriage({
      action_plan: {
        decision_summary: 'All intake safety checks verified clear. EWS band: RED.',
        assumptions: ['[ASSUMED DEMO DEFAULT] Systolic BP: 120 mmHg (not measured)'],
        immediate_actions: [
          {
            urgency: 'routine',
            title: 'Proceed with protocol',
            description: 'No blocking safety alerts detected.',
            reason: 'All intake safety checks passed clear.',
          },
        ],
        medications: [
          {
            medication_name: 'epinephrine',
            dose: '0.5 mg',
            route: 'im',
            timing: 'Immediate',
            indication: 'Administer intramuscular epinephrine',
            contraindications: [],
            warnings: [],
          },
        ],
        monitoring_steps: [
          {
            monitor: 'Vital signs (HR, BP, RR, SpO2)',
            frequency: 'Every 5 minutes',
            trigger: 'Continuous monitoring',
            reason: 'Early warning score band is RED',
          },
        ],
        escalation_steps: [
          {
            when: 'Early warning score band is RED',
            escalate_to: 'Medical Emergency Team',
            reason: 'DENOTES CRITICAL INSTABILITY',
          },
        ],
      },
    } as unknown as Partial<TriageResponse>)
    render(<ExplanationSection triage={mock} />)

    expect(screen.getByText(/Step-by-Step Clinical Action Plan/i)).toBeInTheDocument()
    expect(screen.getByText(/All intake safety checks verified clear/i)).toBeInTheDocument()
    expect(screen.getByText(/Proceed with protocol/i)).toBeInTheDocument()
    expect(screen.getAllByText(/epinephrine/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/0\.5 mg/i)).toBeInTheDocument()
    expect(screen.getByText(/Assumed Demo Defaults:/i)).toBeInTheDocument()
  })
})
