import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SkippedChecksList, type SkippedCheck } from './SkippedChecksList'

describe('SkippedChecksList Component Tests', () => {
  it('returns null when skippedChecks is empty', () => {
    const { container } = render(<SkippedChecksList skippedChecks={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders count of unverified checks and fail closed banner', () => {
    const checks: SkippedCheck[] = [
      {
        rule_id: 'ALLERGY_PENICILLIN',
        rule_type: 'allergy',
        reason: 'Allergy history status is incomplete',
      },
      {
        rule_id: 'EWS_ADULT',
        rule_type: 'physiological_scoring',
        reason: 'Missing blood pressure vitals',
        missing_fields: ['systolic_bp'],
      },
    ]

    render(<SkippedChecksList skippedChecks={checks} />)

    expect(screen.getByText(/Unverified Safety Checks \(2\) • Fail Closed/i)).toBeInTheDocument()
    expect(screen.getByText(/Rule R2 Fail-Closed protocol/i)).toBeInTheDocument()
    expect(screen.getByText('ALLERGY_PENICILLIN')).toBeInTheDocument()
    expect(screen.getByText('EWS_ADULT')).toBeInTheDocument()
  })

  it('renders missing fields badge for skipped checks', () => {
    const checks: SkippedCheck[] = [
      {
        rule_id: 'INTAKE_PATIENT_WEIGHT',
        rule_type: 'vitals_verification',
        reason: 'Patient weight is unknown or unmeasured',
        missing_fields: ['weight_kg'],
      },
    ]

    render(<SkippedChecksList skippedChecks={checks} />)

    expect(screen.getByText('INTAKE_PATIENT_WEIGHT')).toBeInTheDocument()
    expect(screen.getByText('Missing:')).toBeInTheDocument()
    expect(screen.getByText('weight_kg')).toBeInTheDocument()
  })

  it('calls onFixInIntake callback when button is clicked', () => {
    const onFixMock = vi.fn()
    const checks: SkippedCheck[] = [
      {
        rule_id: 'INTAKE_ALLERGY_HISTORY',
        rule_type: 'history_verification',
        reason: 'Allergy history unknown',
      },
    ]

    render(<SkippedChecksList skippedChecks={checks} onFixInIntake={onFixMock} />)

    const fixButton = screen.getByRole('button', { name: /Fix in Intake/i })
    expect(fixButton).toBeInTheDocument()
    fireEvent.click(fixButton)
    expect(onFixMock).toHaveBeenCalledTimes(1)
  })
})
