import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { VerifiedPlanView } from './VerifiedPlanView'
import type { VerifiedStep } from '@/lib/api'

describe('VerifiedPlanView Component Tests', () => {
  it('renders empty placeholder when no steps are provided', () => {
    render(<VerifiedPlanView steps={[]} />)
    expect(screen.getByText(/No protocol orders were generated or verified for this case/i)).toBeInTheDocument()
  })

  it('renders APPROVED step with "Passed Configured Software Checks" badge', () => {
    const steps: VerifiedStep[] = [
      {
        draft: {
          step_number: 1,
          action_type: 'administer',
          drug_id: 'epinephrine',
          narrative_instruction: 'Administer epinephrine 0.5 mg IM',
          requested_dose: { amount: '0.5', unit: 'mg' },
          route: 'im',
          citations: [
            {
              doc_id: 'DOC_01',
              chunk_id: 'CHUNK_01',
              section: 'Dosing',
              quoted_span: 'Administer epinephrine 0.5 mg IM promptly.',
            },
          ],
        },
        status: 'APPROVED',
        triggered_rule_ids: [],
        rejection_reasons: [],
        citation_verified: true,
      },
    ]

    render(<VerifiedPlanView steps={steps} />)
    expect(screen.getByText(/Passed Configured Software Checks/i)).toBeInTheDocument()
    expect(screen.getByText(/Administer epinephrine 0.5 mg IM/i)).toBeInTheDocument()
    expect(screen.getByText(/Order:/i)).toBeInTheDocument()
  })

  it('renders BLOCKED_STRUCK_THROUGH step with strikethrough styling and reasons', () => {
    const steps: VerifiedStep[] = [
      {
        draft: {
          step_number: 2,
          action_type: 'administer',
          drug_id: 'nitroglycerin',
          narrative_instruction: 'Administer nitroglycerin sublingually',
          citations: [],
        },
        status: 'BLOCKED_STRUCK_THROUGH',
        triggered_rule_ids: ['DDI_SILDENAFIL_NITRATES'],
        rejection_reasons: ['Concomitant PDE5 inhibitor within 24 hours (Rule R11: Overrides prohibited)'],
        citation_verified: true,
      },
    ]

    render(<VerifiedPlanView steps={steps} />)
    expect(screen.getByText(/Blocked by Configured Rule/i)).toBeInTheDocument()
    expect(screen.getByText(/Concomitant PDE5 inhibitor within 24 hours/i)).toBeInTheDocument()
  })

  it('renders FLAGGED_HIGH step with "High-Severity Warning" badge', () => {
    const steps: VerifiedStep[] = [
      {
        draft: {
          step_number: 3,
          action_type: 'administer',
          drug_id: 'ceftriaxone',
          narrative_instruction: 'Administer ceftriaxone 1g IV',
          citations: [],
        },
        status: 'FLAGGED_HIGH',
        triggered_rule_ids: ['ALLERGY_PENICILLIN_CEPHALOSPORIN'],
        rejection_reasons: ['Cross-reactivity warning: logged override required'],
        citation_verified: true,
      },
    ]

    render(<VerifiedPlanView steps={steps} />)
    expect(screen.getByText(/High-Severity Warning/i)).toBeInTheDocument()
    expect(screen.getByText(/Cross-reactivity warning: logged override required/i)).toBeInTheDocument()
  })

  it('renders REQUIRES_CLINICIAN_CONFIRMATION badge for inferred syndrome steps', () => {
    const steps: VerifiedStep[] = [
      {
        draft: {
          step_number: 1,
          action_type: 'administer',
          drug_id: 'salbutamol',
          narrative_instruction: 'Administer nebulized salbutamol 2.5 mg',
          citations: [],
        },
        status: 'REQUIRES_CLINICIAN_CONFIRMATION',
        triggered_rule_ids: [],
        rejection_reasons: ['Syndrome inferred from physiological flags (ADR-0007)'],
        citation_verified: true,
      },
    ]

    render(<VerifiedPlanView steps={steps} />)
    expect(screen.getByText(/Requires Clinician Confirmation/i)).toBeInTheDocument()
    expect(screen.getByText(/Syndrome inferred from physiological flags/i)).toBeInTheDocument()
  })

  it('toggles citation verification drawer and displays quoted span', () => {
    const steps: VerifiedStep[] = [
      {
        draft: {
          step_number: 1,
          action_type: 'administer',
          drug_id: 'epinephrine',
          narrative_instruction: 'Administer epinephrine 0.5 mg IM',
          citations: [
            {
              doc_id: 'SYNTH_ANAPHYLAXIS_01',
              chunk_id: 'CHUNK_ANAPH_01',
              section: 'Primary Emergency Resuscitation',
              quoted_span: 'Administer epinephrine 0.5 mg IM immediately into mid-anterolateral thigh.',
            },
          ],
        },
        status: 'APPROVED',
        triggered_rule_ids: [],
        rejection_reasons: [],
        citation_verified: true,
      },
    ]

    render(<VerifiedPlanView steps={steps} />)
    const citationButton = screen.getByRole('button', { name: /Citation/i })
    expect(citationButton).toBeInTheDocument()

    // Expand citation details
    fireEvent.click(citationButton)
    expect(screen.getByText(/SYNTH_ANAPHYLAXIS_01/i)).toBeInTheDocument()
    expect(screen.getByText(/CHUNK_ANAPH_01/i)).toBeInTheDocument()
    expect(screen.getByText(/Administer epinephrine 0.5 mg IM immediately into mid-anterolateral thigh/i)).toBeInTheDocument()
  })
})
