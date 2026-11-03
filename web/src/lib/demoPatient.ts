import type { TriageApiRequest, ScenarioDetail } from '@/lib/api'

/**
 * Canonical Synthetic Demo Patient Request.
 *
 * Safety & Governance:
 * - Uses 100% synthetic patient data based on repository reference scenario BLOCK.
 * - 58-year-old male presenting with acute ischemic chest pain.
 * - Home medication: Silagra (Sildenafil 50mg) taken 12 hours ago (within 24h lookback window).
 * - Known allergy: None (confirmed NKDA).
 * - Vitals: Measured hemodynamics with normal/elevated BP (138/84), normal SpO2 (97%), alert consciousness.
 * - Unknowns preserved: Capillary glucose and GCS are unknown (not silently defaulted to normal).
 * - Chief complaint quarantined: Never passed to engine, retrieval, or LLM by default (Rule R7).
 * - Disclaimer: Research prototype. Synthetic data only. Not a medical device. Not for clinical use.
 */
export const createSyntheticDemoRequest = (): TriageApiRequest => {
  const now = new Date()
  const twelveHoursAgo = new Date(now.getTime() - 12 * 60 * 60 * 1000)

  return {
    patient: {
      assessed_at: now.toISOString(),
      age: { value: '58', unit: 'years' },
      sex: 'male',
      pregnancy: 'no',
      weight_kg: { value: '82.0', source: 'measured' },
      vitals: {
        heart_rate_bpm: { value: 92, source: 'measured' },
        systolic_bp_mmhg: { value: 138, source: 'measured' },
        diastolic_bp_mmhg: { value: 84, source: 'measured' },
        respiratory_rate_bpm: { value: 18, source: 'measured' },
        spo2_percent: { value: 97, source: 'measured' },
        supplemental_o2: { value: 'no', source: 'measured' },
        temperature_c: { value: '37.1', source: 'measured' },
        blood_glucose_mg_dl: { value: null, source: 'unknown' },
        consciousness: { value: 'A', source: 'measured' },
        gcs_total: { value: null, source: 'unknown' },
      },
      medication_history_status: 'confirmed_list',
      medications: [
        {
          raw_text: 'Silagra (Sildenafil 50mg)',
          last_dose_time: twelveHoursAgo.toISOString(),
        },
      ],
      allergy_history_status: 'confirmed_nkda',
      allergies: [],
      suspected_syndrome: 'chest_pain',
      renal_impairment: 'no',
      hepatic_impairment: 'no',
      chief_complaint_untrusted: 'Substernal chest pressure for 2 hours radiating to left jaw',
    },
    llm_profile: 'COMPLIANT',
    include_complaint_in_llm: false,
    overrides: [],
  }
}

export const DEMO_SCENARIO_METADATA: ScenarioDetail = {
  id: 'BLOCK',
  title: 'Drug-Drug Interaction (BLOCK)',
  description: '58-year-old male with acute chest pain who took Silagra (Sildenafil 50mg) 12 hours ago.',
  what_it_demonstrates:
    'Rule R11: Deterministic contraindication blocking Nitroglycerin with no override allowed. All checks and verdicts come from deterministic code—not from an LLM or this demo button.',
  expected_verdict: 'BLOCKED',
  patient: createSyntheticDemoRequest().patient as unknown as ScenarioDetail['patient'],
  overrides: [],
}

export const DEMO_DISCLAIMER =
  'Research prototype. Synthetic data only. Not a medical device. Not for clinical use.'

