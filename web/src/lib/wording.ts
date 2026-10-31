/**
 * Clinical safety wording map and enforcement.
 * Enforces UX Safety Principle: Never render the bare word "CLEAR".
 * Always qualify safety verdicts with rule coverage or unresolved data notice.
 */

import wordingData from './wording.json'

export const MANDATORY_DISCLAIMER: string =
  wordingData.disclaimer ||
  'Research prototype. Synthetic data only. Not a medical device. Not for clinical use.'

export const VERDICT_CONTRACT = wordingData

export const VERDICT_WORDING = {
  BLOCK: wordingData.verdicts.BLOCKED.display,
  HIGH: wordingData.auxiliary.HIGH,
  MODERATE: wordingData.auxiliary.MODERATE,
  INFO: wordingData.auxiliary.INFO,
  UNVERIFIED: wordingData.verdicts.UNVERIFIED.display,
  NO_RULES_FIRED: wordingData.auxiliary.NO_RULES_FIRED,
  CHECKED_ALERTS: wordingData.verdicts.CHECKED_ALERTS.display,
  CHECKED_CLEAR: (ruleCount?: number) =>
    ruleCount !== undefined
      ? wordingData.verdicts.CHECKED_CLEAR.display_with_count.replace('{ruleCount}', String(ruleCount))
      : wordingData.verdicts.CHECKED_CLEAR.display,
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
