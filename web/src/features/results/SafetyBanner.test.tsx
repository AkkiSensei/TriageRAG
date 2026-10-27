import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SafetyBanner } from './SafetyBanner'
import type { EngineReport } from '@/lib/api'

describe('SafetyBanner UX Safety Principle Tests', () => {
  it('renders BLOCKED verdict prominently with contraindication notice', () => {
    const report: EngineReport = {
      verdict: 'BLOCKED',
      checks_run: 15,
      checks_skipped: [],
      baseline_alerts: [],
      plan_alerts: [],
    }

    render(<SafetyBanner report={report} />)

    expect(screen.getAllByText(/BLOCKED/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/CRITICAL SAFETY CONTRAINDICATION/i)).toBeInTheDocument()
  })

  it('renders UNVERIFIED verdict with fail closed notice', () => {
    const report: EngineReport = {
      verdict: 'UNVERIFIED',
      checks_run: 12,
      checks_skipped: [
        {
          rule_id: 'ALLERGY_PENICILLIN_AMOX',
          rule_type: 'allergy',
          reason: 'Allergy history status is incomplete',
        },
      ],
      baseline_alerts: [],
      plan_alerts: [],
    }

    render(<SafetyBanner report={report} />)

    expect(screen.getAllByText(/UNVERIFIED/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/SAFETY CHECKS UNVERIFIED/i)).toBeInTheDocument()
    expect(screen.getByText(/Skipped: 1/i)).toBeInTheDocument()
  })

  it('renders CHECKED CLEAR with ruleset coverage and NEVER bare CLEAR', () => {
    const report: EngineReport = {
      verdict: 'CHECKED_CLEAR',
      checks_run: 20,
      checks_skipped: [],
      baseline_alerts: [],
      plan_alerts: [],
    }

    const { container } = render(<SafetyBanner report={report} />)

    expect(screen.getByText(/CHECKED CLEAR/i)).toBeInTheDocument()
    // Must NOT have bare isolated "CLEAR"
    const textContent = container.textContent || ''
    expect(textContent).toContain('CHECKED CLEAR')
    expect(/\bCLEAR\b/.test(textContent.replace('CHECKED CLEAR', ''))).toBe(false)
  })
})
