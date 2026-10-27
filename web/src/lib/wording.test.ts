import { describe, it, expect } from 'vitest'
import {
  MANDATORY_DISCLAIMER,
  VERDICT_WORDING,
  formatSafetyVerdict,
  assertNoBareClear,
} from './wording'

describe('Clinical Wording Safety Guarantees', () => {
  it('never outputs bare "CLEAR" for safe verdicts', () => {
    const verdict = formatSafetyVerdict('CLEAR')
    expect(verdict).not.toBe('CLEAR')
    expect(verdict).toContain('CHECKED CLEAR')
    expect(assertNoBareClear(verdict)).toBe(true)
  })

  it('includes rule coverage count when provided', () => {
    const verdict = formatSafetyVerdict('CLEAR', 12)
    expect(verdict).toBe('CHECKED CLEAR (ruleset coverage: 12 active rules)')
    expect(assertNoBareClear(verdict)).toBe(true)
  })

  it('formats BLOCK and HIGH verdicts with safety qualifiers', () => {
    expect(formatSafetyVerdict('BLOCK')).toBe(VERDICT_WORDING.BLOCK)
    expect(formatSafetyVerdict('HIGH')).toBe(VERDICT_WORDING.HIGH)
    expect(formatSafetyVerdict('UNVERIFIED')).toBe(VERDICT_WORDING.UNVERIFIED)
    expect(formatSafetyVerdict('NO_RULES_FIRED')).toBe(VERDICT_WORDING.NO_RULES_FIRED)
  })

  it('detects and flags bare CLEAR with assertNoBareClear', () => {
    expect(assertNoBareClear('Patient status: CLEAR')).toBe(false)
    expect(assertNoBareClear('Drug check: CLEAR')).toBe(false)
    expect(assertNoBareClear('CHECKED CLEAR (ruleset coverage: 5 rules)')).toBe(true)
    expect(assertNoBareClear('BLOCKED (contraindication)')).toBe(true)
  })

  it('mandatory disclaimer contains all non-negotiable clauses', () => {
    expect(MANDATORY_DISCLAIMER).toContain('Research prototype')
    expect(MANDATORY_DISCLAIMER).toContain('Synthetic data only')
    expect(MANDATORY_DISCLAIMER).toContain('Not a medical device')
    expect(MANDATORY_DISCLAIMER).toContain('Not for clinical use')
  })
})
