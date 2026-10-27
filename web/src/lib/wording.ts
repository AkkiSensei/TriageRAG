/**
 * Clinical safety wording map and enforcement.
 * Enforces UX Safety Principle: Never render the bare word "CLEAR".
 * Always qualify safety verdicts with rule coverage or unresolved data notice.
 */

export const MANDATORY_DISCLAIMER =
  'Research prototype. Synthetic data only. Not a medical device. Not for clinical use.'

export const VERDICT_WORDING = {
  BLOCK: 'BLOCKED (contraindication / unsafe)',
  HIGH: 'HIGH ALERT (override required)',
  MODERATE: 'MODERATE ALERT',
  INFO: 'INFORMATION',
  UNVERIFIED: 'UNVERIFIED (missing/unresolved data)',
  NO_RULES_FIRED: 'NO RULES FIRED IN THIS RULESET',
  CHECKED_ALERTS: 'CHECKED WITH ACTIVE ALERTS',
  CHECKED_CLEAR: (ruleCount?: number) =>
    ruleCount !== undefined
      ? `CHECKED CLEAR (ruleset coverage: ${ruleCount} active rules)`
      : 'CHECKED CLEAR (within current ruleset coverage)',
} as const

export type VerdictType =
  | 'BLOCK'
  | 'HIGH'
  | 'MODERATE'
  | 'INFO'
  | 'UNVERIFIED'
  | 'NO_RULES_FIRED'
  | 'CHECKED_ALERTS'
  | 'CHECKED_CLEAR'

/**
 * Maps a safety verdict string to human-readable clinical copy.
 * Strictly guarantees that bare "CLEAR" is never returned.
 */
export function formatSafetyVerdict(verdict: string, ruleCount?: number): string {
  const normalized = verdict.toUpperCase().trim()

  if (
    normalized === 'CLEAR' ||
    normalized === 'SAFE' ||
    normalized === 'PASS' ||
    normalized === 'CHECKED_CLEAR'
  ) {
    return VERDICT_WORDING.CHECKED_CLEAR(ruleCount)
  }
  if (normalized === 'BLOCK' || normalized === 'BLOCKED') {
    return VERDICT_WORDING.BLOCK
  }
  if (normalized === 'HIGH') {
    return VERDICT_WORDING.HIGH
  }
  if (normalized === 'MODERATE') {
    return VERDICT_WORDING.MODERATE
  }
  if (normalized === 'INFO') {
    return VERDICT_WORDING.INFO
  }
  if (normalized === 'UNVERIFIED') {
    return VERDICT_WORDING.UNVERIFIED
  }
  if (normalized === 'NO_RULES_FIRED') {
    return VERDICT_WORDING.NO_RULES_FIRED
  }
  if (normalized === 'CHECKED_ALERTS') {
    return VERDICT_WORDING.CHECKED_ALERTS
  }

  // Safety fallback: if string contains bare CLEAR, replace it
  if (/\bCLEAR\b/.test(normalized) && !normalized.includes('CHECKED CLEAR')) {
    return VERDICT_WORDING.CHECKED_CLEAR(ruleCount)
  }
  return verdict
}

/**
 * Assertive helper used in tests and components to ensure no bare "CLEAR" is rendered.
 */
export function assertNoBareClear(text: string): boolean {
  // Regex looks for isolated "CLEAR"
  const regex = /\bCLEAR\b/i
  if (regex.test(text) && !text.toUpperCase().includes('CHECKED CLEAR')) {
    return false
  }
  return true
}
