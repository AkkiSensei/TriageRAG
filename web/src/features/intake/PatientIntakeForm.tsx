import React, { useState, useEffect } from 'react'
import { MeasuredInput, type MeasurementStatus } from './MeasuredInput'
import type { TriageApiRequest, ScenarioDetail } from '@/lib/api'
import type { components } from '@/types/api'
import {
  Plus,
  Trash2,
  RotateCcw,
  Stethoscope,
  Pill,
  ShieldCheck,
  FileText,
  Activity,
  ArrowRight,
  Clock,
  Loader2,
  AlertCircle,
  ShieldAlert,
} from 'lucide-react'

type AgeUnit = components['schemas']['AgeUnit']
type Sex = 'male' | 'female' | 'other' | 'unknown'
type Pregnancy = 'yes' | 'no' | 'not_applicable' | 'unknown'
type Consciousness = components['schemas']['Consciousness']
type HistoryStatus =
  | 'confirmed_none'
  | 'confirmed_nkda'
  | 'confirmed_list'
  | 'incomplete'
  | 'unknown_unobtainable'
type ReactionType =
  | 'anaphylaxis_ige'
  | 'severe_cutaneous_scar'
  | 'mild_rash'
  | 'gi_upset'
  | 'unknown'
type Impairment = 'yes' | 'no' | 'unknown'
type LLMProfile =
  | 'COMPLIANT'
  | 'INVENT_DRUG'
  | 'PROSE_LEAK'
  | 'INVALID_CITATION'
  | 'IGNORE_BLOCK'
  | 'OBEY_COMPLAINT'
  | 'NAIVE_FREE_TEXT'

export interface IntakeMedication {
  raw_string: string
  last_dose_hours_ago: number | null
}

export interface IntakeAllergy {
  raw_substance: string
  reaction_type: ReactionType
}

export interface FormState {
  ageValue: string
  ageUnit: AgeUnit
  sex: Sex
  pregnancy: Pregnancy
  weightStatus: MeasurementStatus
  weightValue: string

  // Vitals
  hrStatus: MeasurementStatus
  hrValue: number | null
  sbpStatus: MeasurementStatus
  sbpValue: number | null
  dbpStatus: MeasurementStatus
  dbpValue: number | null
  rrStatus: MeasurementStatus
  rrValue: number | null
  spo2Status: MeasurementStatus
  spo2Value: number | null
  o2Status: MeasurementStatus
  o2Value: 'yes' | 'no' | 'unknown'
  tempStatus: MeasurementStatus
  tempValue: string
  glucoseStatus: MeasurementStatus
  glucoseValue: string
  consciousnessStatus: MeasurementStatus
  consciousnessValue: Consciousness

  // Medication history
  medicationStatus: HistoryStatus
  medications: IntakeMedication[]

  // Allergy history
  allergyStatus: HistoryStatus
  allergies: IntakeAllergy[]

  // Clinical context
  suspectedSyndrome: string
  renalImpairment: Impairment
  hepaticImpairment: Impairment

  // Triage narrative
  chiefComplaint: string
  includeComplaintInLlm: boolean
  llmProfile: LLMProfile
}

export const INITIAL_FORM_STATE: FormState = {
  ageValue: '62',
  ageUnit: 'years',
  sex: 'male',
  pregnancy: 'no',
  weightStatus: 'measured',
  weightValue: '82.0',

  hrStatus: 'measured',
  hrValue: 92,
  sbpStatus: 'measured',
  sbpValue: 135,
  dbpStatus: 'measured',
  dbpValue: 85,
  rrStatus: 'measured',
  rrValue: 18,
  spo2Status: 'measured',
  spo2Value: 98,
  o2Status: 'measured',
  o2Value: 'no',
  tempStatus: 'measured',
  tempValue: '37.1',
  glucoseStatus: 'measured',
  glucoseValue: '110.0',
  consciousnessStatus: 'measured',
  consciousnessValue: 'A',

  medicationStatus: 'confirmed_none',
  medications: [],

  allergyStatus: 'confirmed_nkda',
  allergies: [],

  suspectedSyndrome: 'chest_pain',
  renalImpairment: 'no',
  hepaticImpairment: 'no',

  chiefComplaint: 'Patient presents with acute retrosternal chest pressure radiating to left arm.',
  includeComplaintInLlm: false,
  llmProfile: 'COMPLIANT',
}

const COMMON_DRUGS = [
  'Sildenafil',
  'Viagra',
  'Cialis (Tadalafil)',
  'Nitroglycerin',
  'Metoprolol',
  'Lisinopril',
  'Amoxicillin',
  'Augmentin',
  'Salbutamol',
  'Epinephrine',
  'Ceftriaxone',
  'Dextrose',
]

interface PatientIntakeFormProps {
  onSubmit: (request: TriageApiRequest) => void
  isLoading?: boolean
  initialScenario?: ScenarioDetail | null
  existingRequest?: TriageApiRequest | null
  errorMessage?: string | null
}

export const PatientIntakeForm: React.FC<PatientIntakeFormProps> = ({
  onSubmit,
  isLoading,
  initialScenario,
  existingRequest,
  errorMessage,
}) => {
  const [form, setForm] = useState<FormState>(INITIAL_FORM_STATE)

  // Quick inputs
  const [newMedName, setNewMedName] = useState('')
  const [newMedLastDose, setNewMedLastDose] = useState<number | null>(12)
  const [newAllergySubstance, setNewAllergySubstance] = useState('')
  const [newAllergyReaction, setNewAllergyReaction] = useState<ReactionType>('anaphylaxis_ige')

  // Auto-enforce biological invariant for pregnancy
  const handleSexChange = (newSex: Sex) => {
    setForm((prev) => ({
      ...prev,
      sex: newSex,
      pregnancy: newSex === 'male' ? 'no' : prev.pregnancy,
    }))
  }

  // Populate from existing request or scenario
  useEffect(() => {
    if (existingRequest) {
      loadRequestState(existingRequest)
    } else if (initialScenario) {
      loadScenarioState(initialScenario)
    }
  }, [initialScenario, existingRequest])

  const loadScenarioState = (scenario: ScenarioDetail) => {
    const p = scenario.patient
    const rawConsciousness = (p.vitals.consciousness?.value as string) || 'A'
    const validConsciousness: Consciousness =
      rawConsciousness === 'A' ||
      rawConsciousness === 'C' ||
      rawConsciousness === 'V' ||
      rawConsciousness === 'P' ||
      rawConsciousness === 'U'
        ? (rawConsciousness as Consciousness)
        : 'A'

    const patientSex = (p.sex as Sex) || 'male'

    setForm({
      ageValue: String(p.age.value),
      ageUnit: (p.age.unit as AgeUnit) || 'years',
      sex: patientSex,
      pregnancy: patientSex === 'male' ? 'no' : ((p.pregnancy as Pregnancy) || 'no'),
      weightStatus: (p.weight_kg.source as MeasurementStatus) || 'measured',
      weightValue:
        p.weight_kg.value !== null && p.weight_kg.value !== undefined
          ? String(p.weight_kg.value)
          : '',

      hrStatus: (p.vitals.heart_rate_bpm?.source as MeasurementStatus) || 'unknown',
      hrValue: p.vitals.heart_rate_bpm?.value ?? null,
      sbpStatus: (p.vitals.systolic_bp_mmhg?.source as MeasurementStatus) || 'unknown',
      sbpValue: p.vitals.systolic_bp_mmhg?.value ?? null,
      dbpStatus: (p.vitals.diastolic_bp_mmhg?.source as MeasurementStatus) || 'unknown',
      dbpValue: p.vitals.diastolic_bp_mmhg?.value ?? null,
      rrStatus: (p.vitals.respiratory_rate_bpm?.source as MeasurementStatus) || 'unknown',
      rrValue: p.vitals.respiratory_rate_bpm?.value ?? null,
      spo2Status: (p.vitals.spo2_percent?.source as MeasurementStatus) || 'unknown',
      spo2Value: p.vitals.spo2_percent?.value ?? null,
      o2Status: (p.vitals.supplemental_o2?.source as MeasurementStatus) || 'unknown',
      o2Value: (p.vitals.supplemental_o2?.value as 'yes' | 'no' | 'unknown') || 'unknown',
      tempStatus: (p.vitals.temperature_c?.source as MeasurementStatus) || 'unknown',
      tempValue:
        p.vitals.temperature_c?.value !== null && p.vitals.temperature_c?.value !== undefined
          ? String(p.vitals.temperature_c.value)
          : '',
      glucoseStatus: (p.vitals.blood_glucose_mg_dl?.source as MeasurementStatus) || 'unknown',
      glucoseValue:
        p.vitals.blood_glucose_mg_dl?.value !== null &&
        p.vitals.blood_glucose_mg_dl?.value !== undefined
          ? String(p.vitals.blood_glucose_mg_dl.value)
          : '',
      consciousnessStatus: (p.vitals.consciousness?.source as MeasurementStatus) || 'unknown',
      consciousnessValue: validConsciousness,

      medicationStatus: (p.medication_history_status as HistoryStatus) || 'confirmed_none',
      medications: (p.medications || []).map((m) => {
        let hoursAgo: number | null = null
        if (m.last_dose_time) {
          const doseDate = new Date(m.last_dose_time)
          const assessDate = new Date(p.assessed_at)
          const diffMs = assessDate.getTime() - doseDate.getTime()
          hoursAgo = Math.max(0, Math.round(diffMs / (1000 * 60 * 60)))
        }
        return {
          raw_string: m.raw_text,
          last_dose_hours_ago: hoursAgo,
        }
      }),

      allergyStatus: (p.allergy_history_status as HistoryStatus) || 'confirmed_nkda',
      allergies: (p.allergies || []).map((a) => ({
        raw_substance: a.raw_substance,
        reaction_type: (a.reaction_type as ReactionType) || 'unknown',
      })),

      suspectedSyndrome: p.suspected_syndrome || 'chest_pain',
      renalImpairment: (p.renal_impairment as Impairment) || 'no',
      hepaticImpairment: (p.hepatic_impairment as Impairment) || 'no',

      chiefComplaint: p.chief_complaint_untrusted || '',
      includeComplaintInLlm: false,
      llmProfile: 'COMPLIANT',
    })
  }

  const loadRequestState = (req: TriageApiRequest) => {
    const p = req.patient
    const rawConsciousness = (p.vitals.consciousness?.value as string) || 'A'
    const validConsciousness: Consciousness =
      rawConsciousness === 'A' ||
      rawConsciousness === 'C' ||
      rawConsciousness === 'V' ||
      rawConsciousness === 'P' ||
      rawConsciousness === 'U'
        ? (rawConsciousness as Consciousness)
        : 'A'

    const patientSex = (p.sex as Sex) || 'male'

    setForm({
      ageValue: String(p.age.value),
      ageUnit: (p.age.unit as AgeUnit) || 'years',
      sex: patientSex,
      pregnancy: patientSex === 'male' ? 'no' : ((p.pregnancy as Pregnancy) || 'no'),
      weightStatus: (p.weight_kg.source as MeasurementStatus) || 'measured',
      weightValue:
        p.weight_kg.value !== null && p.weight_kg.value !== undefined
          ? String(p.weight_kg.value)
          : '',

      hrStatus: (p.vitals.heart_rate_bpm?.source as MeasurementStatus) || 'unknown',
      hrValue: p.vitals.heart_rate_bpm?.value ?? null,
      sbpStatus: (p.vitals.systolic_bp_mmhg?.source as MeasurementStatus) || 'unknown',
      sbpValue: p.vitals.systolic_bp_mmhg?.value ?? null,
      dbpStatus: (p.vitals.diastolic_bp_mmhg?.source as MeasurementStatus) || 'unknown',
      dbpValue: p.vitals.diastolic_bp_mmhg?.value ?? null,
      rrStatus: (p.vitals.respiratory_rate_bpm?.source as MeasurementStatus) || 'unknown',
      rrValue: p.vitals.respiratory_rate_bpm?.value ?? null,
      spo2Status: (p.vitals.spo2_percent?.source as MeasurementStatus) || 'unknown',
      spo2Value: p.vitals.spo2_percent?.value ?? null,
      o2Status: (p.vitals.supplemental_o2?.source as MeasurementStatus) || 'unknown',
      o2Value: (p.vitals.supplemental_o2?.value as 'yes' | 'no' | 'unknown') || 'unknown',
      tempStatus: (p.vitals.temperature_c?.source as MeasurementStatus) || 'unknown',
      tempValue:
        p.vitals.temperature_c?.value !== null && p.vitals.temperature_c?.value !== undefined
          ? String(p.vitals.temperature_c.value)
          : '',
      glucoseStatus: (p.vitals.blood_glucose_mg_dl?.source as MeasurementStatus) || 'unknown',
      glucoseValue:
        p.vitals.blood_glucose_mg_dl?.value !== null &&
        p.vitals.blood_glucose_mg_dl?.value !== undefined
          ? String(p.vitals.blood_glucose_mg_dl.value)
          : '',
      consciousnessStatus: (p.vitals.consciousness?.source as MeasurementStatus) || 'unknown',
      consciousnessValue: validConsciousness,

      medicationStatus: (p.medication_history_status as HistoryStatus) || 'confirmed_none',
      medications: (p.medications || []).map((m) => {
        let hoursAgo: number | null = null
        if (m.last_dose_time) {
          const doseDate = new Date(m.last_dose_time)
          const assessDate = new Date(p.assessed_at)
          const diffMs = assessDate.getTime() - doseDate.getTime()
          hoursAgo = Math.max(0, Math.round(diffMs / (1000 * 60 * 60)))
        }
        return {
          raw_string: m.raw_text,
          last_dose_hours_ago: hoursAgo,
        }
      }),

      allergyStatus: (p.allergy_history_status as HistoryStatus) || 'confirmed_nkda',
      allergies: (p.allergies || []).map((a) => ({
        raw_substance: a.raw_substance,
        reaction_type: (a.reaction_type as ReactionType) || 'unknown',
      })),

      suspectedSyndrome: p.suspected_syndrome || 'chest_pain',
      renalImpairment: (p.renal_impairment as Impairment) || 'no',
      hepaticImpairment: (p.hepatic_impairment as Impairment) || 'no',

      chiefComplaint: p.chief_complaint_untrusted || '',
      includeComplaintInLlm: req.include_complaint_in_llm || false,
      llmProfile: (req.llm_profile as LLMProfile) || 'COMPLIANT',
    })
  }

  const cleanMeasuredDecimal = (valStr: string, status: MeasurementStatus): { value: string | null; source: MeasurementStatus } => {
    if (status === 'unknown' || !valStr.trim()) {
      return { value: null, source: 'unknown' }
    }
    const num = parseFloat(valStr)
    return {
      value: isNaN(num) ? null : valStr.trim(),
      source: status,
    }
  }

  const cleanMeasuredInt = (val: number | null, status: MeasurementStatus): { value: number | null; source: MeasurementStatus } => {
    if (status === 'unknown' || val === null || val === undefined || isNaN(val)) {
      return { value: null, source: 'unknown' }
    }
    return {
      value: Math.round(val),
      source: status,
    }
  }

  const buildApiPayload = (): TriageApiRequest => {
    const assessedAt = new Date().toISOString()
    const assessedMs = new Date(assessedAt).getTime()

    // 1. Biological age
    const validAge = form.ageValue && !isNaN(parseFloat(form.ageValue)) ? form.ageValue : '62'

    // 2. Sex and pregnancy lock
    const sex = form.sex
    const pregnancy = sex === 'male' ? 'no' : form.pregnancy

    // 3. Supplemental O2
    let o2Payload: { value: 'yes' | 'no' | 'unknown' | null; source: MeasurementStatus }
    if (form.o2Status === 'unknown') {
      o2Payload = { value: null, source: 'unknown' }
    } else {
      o2Payload = { value: form.o2Value, source: form.o2Status }
    }

    // 4. Consciousness
    let consciousnessPayload: { value: Consciousness | null; source: MeasurementStatus }
    if (form.consciousnessStatus === 'unknown') {
      consciousnessPayload = { value: null, source: 'unknown' }
    } else if (['A', 'C', 'V', 'P', 'U'].includes(form.consciousnessValue)) {
      consciousnessPayload = { value: form.consciousnessValue, source: form.consciousnessStatus }
    } else {
      consciousnessPayload = { value: 'A', source: 'measured' }
    }

    // 5. Sanitize medications and reconcile status
    const validMedications = form.medications
      .filter((m) => m && m.raw_string && m.raw_string.trim().length > 0)
      .map((m) => {
        let lastDoseIso: string | null = null
        if (
          m.last_dose_hours_ago !== null &&
          m.last_dose_hours_ago !== undefined &&
          !isNaN(Number(m.last_dose_hours_ago))
        ) {
          const hours = Math.max(0, Number(m.last_dose_hours_ago))
          const timeAgo = new Date(assessedMs - hours * 3600 * 1000)
          lastDoseIso = timeAgo.toISOString()
        }
        return {
          raw_text: m.raw_string.trim(),
          last_dose_time: lastDoseIso,
        }
      })

    let resolvedMedStatus = form.medicationStatus
    if (validMedications.length > 0) {
      if (resolvedMedStatus === 'confirmed_none' || resolvedMedStatus === 'confirmed_nkda') {
        resolvedMedStatus = 'confirmed_list'
      }
    } else {
      if (resolvedMedStatus === 'confirmed_list') {
        resolvedMedStatus = 'confirmed_none'
      }
    }

    // 6. Sanitize allergies and reconcile status
    const validAllergies = form.allergies
      .filter((a) => a && a.raw_substance && a.raw_substance.trim().length > 0)
      .map((a) => ({
        raw_substance: a.raw_substance.trim(),
        reaction_type: a.reaction_type || 'unknown',
      }))

    let resolvedAllergyStatus = form.allergyStatus
    if (validAllergies.length > 0) {
      if (resolvedAllergyStatus === 'confirmed_none' || resolvedAllergyStatus === 'confirmed_nkda') {
        resolvedAllergyStatus = 'confirmed_list'
      }
    } else {
      if (resolvedAllergyStatus === 'confirmed_list') {
        resolvedAllergyStatus = 'confirmed_nkda'
      }
    }

    return {
      patient: {
        assessed_at: assessedAt,
        age: {
          value: validAge,
          unit: form.ageUnit,
        },
        sex,
        pregnancy,
        weight_kg: cleanMeasuredDecimal(form.weightValue, form.weightStatus),
        vitals: {
          heart_rate_bpm: cleanMeasuredInt(form.hrValue, form.hrStatus),
          systolic_bp_mmhg: cleanMeasuredInt(form.sbpValue, form.sbpStatus),
          diastolic_bp_mmhg: cleanMeasuredInt(form.dbpValue, form.dbpStatus),
          respiratory_rate_bpm: cleanMeasuredInt(form.rrValue, form.rrStatus),
          spo2_percent: cleanMeasuredInt(form.spo2Value, form.spo2Status),
          supplemental_o2: o2Payload,
          temperature_c: cleanMeasuredDecimal(form.tempValue, form.tempStatus),
          blood_glucose_mg_dl: cleanMeasuredDecimal(form.glucoseValue, form.glucoseStatus),
          consciousness: consciousnessPayload,
          gcs_total: { value: null, source: 'unknown' },
        },
        medication_history_status: resolvedMedStatus,
        medications: validMedications,
        allergy_history_status: resolvedAllergyStatus,
        allergies: validAllergies,
        suspected_syndrome: form.suspectedSyndrome?.trim() || null,
        renal_impairment: form.renalImpairment || 'no',
        hepatic_impairment: form.hepaticImpairment || 'no',
        chief_complaint_untrusted: form.chiefComplaint?.trim() || '',
      },
      llm_profile: form.llmProfile || 'COMPLIANT',
      include_complaint_in_llm: Boolean(form.includeComplaintInLlm),
      overrides: [],
    }
  }

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    onSubmit(buildApiPayload())
  }

  const addMedication = (name: string, hoursAgo: number | null) => {
    if (!name.trim()) return
    setForm((prev) => ({
      ...prev,
      medications: [...prev.medications, { raw_string: name.trim(), last_dose_hours_ago: hoursAgo }],
      medicationStatus: 'confirmed_list',
    }))
    setNewMedName('')
  }

  const removeMedication = (idx: number) => {
    setForm((prev) => {
      const updated = prev.medications.filter((_, i) => i !== idx)
      return {
        ...prev,
        medications: updated,
        medicationStatus: updated.length === 0 ? 'confirmed_none' : 'confirmed_list',
      }
    })
  }

  const addAllergy = (substance: string, reaction: ReactionType) => {
    if (!substance.trim()) return
    setForm((prev) => ({
      ...prev,
      allergies: [...prev.allergies, { raw_substance: substance.trim(), reaction_type: reaction }],
      allergyStatus: 'confirmed_list',
    }))
    setNewAllergySubstance('')
  }

  const removeAllergy = (idx: number) => {
    setForm((prev) => {
      const updated = prev.allergies.filter((_, i) => i !== idx)
      return {
        ...prev,
        allergies: updated,
        allergyStatus: updated.length === 0 ? 'confirmed_nkda' : 'confirmed_list',
      }
    })
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      {/* CARD 1: PRESENTING CLINICAL SYNDROME */}
      <div className="rounded-2xl border border-[#d9e8e6] bg-white p-5 sm:p-6 shadow-soft">
        <div className="flex items-center justify-between border-b border-[#d9e8e6] pb-3 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
              <Activity className="h-4 w-4" />
            </div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              1. Presenting Clinical Syndrome
            </h3>
          </div>
          <button
            type="button"
            onClick={() => setForm(INITIAL_FORM_STATE)}
            className="flex items-center gap-1 text-[11px] font-mono text-slate-500 hover:text-teal-800 transition-colors"
            title="Reset to default baseline"
          >
            <RotateCcw className="h-3 w-3" />
            <span>Reset Form</span>
          </button>
        </div>

        <div className="flex flex-col gap-3.5">
          {/* Syndrome Dropdown */}
          <div>
            <label className="text-xs font-semibold text-slate-800 flex items-center justify-between">
              <span>Suspected Clinical Syndrome</span>
              <span className="text-[10px] text-teal-700 font-mono font-medium">
                Partitions Emergency Protocols
              </span>
            </label>
            <select
              value={form.suspectedSyndrome}
              onChange={(e) => setForm({ ...form, suspectedSyndrome: e.target.value })}
              className="mt-1 h-10 w-full rounded-xl border border-[#d9e8e6] bg-white px-3 text-xs font-medium text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
            >
              <option value="">None / Unspecified (General Vitals Screening)</option>
              <option value="chest_pain">Acute Chest Pain &amp; Suspected Coronary Syndrome</option>
              <option value="anaphylaxis">Acute Anaphylaxis / Severe Systemic Allergic Reaction</option>
              <option value="severe_asthma">Severe Acute Asthma &amp; Bronchospasm</option>
              <option value="hypoglycemia">Acute Symptomatic Hypoglycemia</option>
              <option value="paediatric_sepsis">Pediatric Sepsis &amp; Febrile Shock</option>
              <option value="altered_mental_status">Altered Mental Status / Acute Confusion</option>
            </select>
          </div>
        </div>
      </div>

      {/* QUARANTINED CHIEF COMPLAINT (RULE R7 QUARANTINE CONTAINER) */}
      <div className="rounded-2xl border-2 border-amber-300 bg-gradient-to-br from-amber-50/70 via-white to-amber-50/40 p-5 shadow-soft">
        <div className="flex items-center justify-between pb-2.5 mb-2 border-b border-amber-200">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-amber-100 text-amber-800">
              <ShieldAlert className="h-3.5 w-3.5" />
            </div>
            <span className="text-xs font-bold uppercase tracking-wider text-amber-900">
              Rule R7 Quarantine: Patient-Reported Chief Complaint
            </span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-200/80 text-amber-950 font-bold">
            UNTRUSTED NARRATIVE
          </span>
        </div>

        <p className="text-[11px] text-amber-900/80 mb-2.5 leading-relaxed">
          <strong>Security Boundary:</strong> Text entered here is quarantined and strictly excluded from rule evaluation, dose math, and retrieval indexes. It will never be rendered as executable markup.
        </p>

        <textarea
          rows={2}
          value={form.chiefComplaint}
          onChange={(e) => setForm({ ...form, chiefComplaint: e.target.value })}
          placeholder="Enter patient narrative or paramedic handoff notes (e.g. 'Sudden onset chest tightness radiating to jaw')..."
          className="w-full rounded-xl border border-amber-300 bg-white p-3 text-xs text-slate-900 placeholder-slate-400 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 resize-none font-sans leading-relaxed"
        />

        <div className="mt-2.5 flex items-center justify-between text-[11px]">
          <label className="flex items-center gap-2 text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={form.includeComplaintInLlm}
              onChange={(e) => setForm({ ...form, includeComplaintInLlm: e.target.checked })}
              className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
            />
            <span className="font-medium text-slate-600">
              Pass to LLM in delimited context block only (disabled by default)
            </span>
          </label>
          <span className="text-[10px] font-mono text-slate-400">
            {form.chiefComplaint.length}/500 chars
          </span>
        </div>
      </div>

      {/* CARD 2: DEMOGRAPHICS & PHYSIOLOGICAL VITALS */}
      <div className="rounded-2xl border border-[#d9e8e6] bg-white p-5 sm:p-6 shadow-soft">
        <div className="flex items-center justify-between border-b border-[#d9e8e6] pb-3 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
              <Stethoscope className="h-4 w-4" />
            </div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              2. Demographics &amp; Physiological Vitals
            </h3>
          </div>
          <span className="text-[11px] font-mono text-teal-700 font-semibold bg-teal-50 px-2 py-0.5 rounded-full border border-teal-200">
            NEWS2 / PEWS Input
          </span>
        </div>

        {/* Demographics Row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          {/* Age */}
          <div>
            <label className="text-[11px] font-semibold text-slate-800">Age</label>
            <div className="mt-1 flex gap-1.5">
              <input
                type="text"
                value={form.ageValue}
                onChange={(e) => setForm({ ...form, ageValue: e.target.value })}
                placeholder="62"
                className="h-10 w-2/3 rounded-xl border border-[#d9e8e6] bg-white px-3 text-xs font-medium text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
              />
              <select
                value={form.ageUnit}
                onChange={(e) => setForm({ ...form, ageUnit: e.target.value as AgeUnit })}
                className="h-10 w-1/3 rounded-xl border border-[#d9e8e6] bg-white px-1.5 text-[11px] font-mono font-medium text-slate-800 focus:border-teal-600 focus:outline-none"
              >
                <option value="years">yr</option>
                <option value="months">mo</option>
                <option value="days">d</option>
              </select>
            </div>
          </div>

          {/* Biological Sex */}
          <div>
            <label className="text-[11px] font-semibold text-slate-800">Biological Sex</label>
            <select
              value={form.sex}
              onChange={(e) => handleSexChange(e.target.value as Sex)}
              className="mt-1 h-10 w-full rounded-xl border border-[#d9e8e6] bg-white px-3 text-xs font-medium text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
            >
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>

          {/* Pregnancy Status (Strictly locked to No for Male) */}
          <div>
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-semibold text-slate-800">Pregnancy</label>
              {form.sex === 'male' && (
                <span className="text-[10px] text-slate-400 font-mono">Auto-Locked</span>
              )}
            </div>
            {form.sex === 'male' ? (
              <div
                className="mt-1 flex h-10 w-full items-center rounded-xl border border-slate-200 bg-slate-50 px-3 text-xs text-slate-500 font-mono cursor-not-allowed select-none"
                title="Biological invariant: Male patients are locked to No"
              >
                No (N/A)
              </div>
            ) : (
              <select
                value={form.pregnancy}
                onChange={(e) => setForm({ ...form, pregnancy: e.target.value as Pregnancy })}
                className="mt-1 h-10 w-full rounded-xl border border-teal-300 bg-white px-3 text-xs font-medium text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
              >
                <option value="no">Not Pregnant (No)</option>
                <option value="yes">Pregnant (Yes)</option>
                <option value="unknown">Unknown</option>
              </select>
            )}
          </div>

          {/* Weight */}
          <div>
            <label className="text-[11px] font-semibold text-slate-800">Weight (kg)</label>
            <input
              type="text"
              value={form.weightValue}
              onChange={(e) => setForm({ ...form, weightValue: e.target.value })}
              placeholder="82.0"
              className="mt-1 h-10 w-full rounded-xl border border-[#d9e8e6] bg-white px-3 text-xs font-medium text-slate-900 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
            />
          </div>
        </div>

        {/* 7 Physiological Vitals Grid */}
        <div className="flex flex-col gap-3 pt-4 border-t border-[#d9e8e6]">
          <span className="text-[11px] font-bold text-slate-800 uppercase tracking-wider">
            Physiological Measurements
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
            <MeasuredInput
              label="Heart Rate"
              unit="bpm"
              type="number"
              status={form.hrStatus}
              value={form.hrValue}
              placeholder="92"
              onStatusChange={(status) => setForm({ ...form, hrStatus: status })}
              onValueChange={(val) => setForm({ ...form, hrValue: val })}
            />
            <MeasuredInput
              label="Systolic BP"
              unit="mmHg"
              type="number"
              status={form.sbpStatus}
              value={form.sbpValue}
              placeholder="135"
              onStatusChange={(status) => setForm({ ...form, sbpStatus: status })}
              onValueChange={(val) => setForm({ ...form, sbpValue: val })}
            />
            <MeasuredInput
              label="Diastolic BP"
              unit="mmHg"
              type="number"
              status={form.dbpStatus}
              value={form.dbpValue}
              placeholder="85"
              onStatusChange={(status) => setForm({ ...form, dbpStatus: status })}
              onValueChange={(val) => setForm({ ...form, dbpValue: val })}
            />
            <MeasuredInput
              label="Resp Rate"
              unit="bpm"
              type="number"
              status={form.rrStatus}
              value={form.rrValue}
              placeholder="18"
              onStatusChange={(status) => setForm({ ...form, rrStatus: status })}
              onValueChange={(val) => setForm({ ...form, rrValue: val })}
            />
            <MeasuredInput
              label="SpO2"
              unit="%"
              type="number"
              status={form.spo2Status}
              value={form.spo2Value}
              placeholder="98"
              onStatusChange={(status) => setForm({ ...form, spo2Status: status })}
              onValueChange={(val) => setForm({ ...form, spo2Value: val })}
            />
            <MeasuredInput
              label="Temperature"
              unit="°C"
              status={form.tempStatus}
              value={form.tempValue}
              placeholder="37.1"
              onStatusChange={(status) => setForm({ ...form, tempStatus: status })}
              onValueChange={(val) => setForm({ ...form, tempValue: val || '' })}
            />
            <MeasuredInput
              label="Blood Glucose"
              unit="mg/dL"
              status={form.glucoseStatus}
              value={form.glucoseValue}
              placeholder="110.0"
              onStatusChange={(status) => setForm({ ...form, glucoseStatus: status })}
              onValueChange={(val) => setForm({ ...form, glucoseValue: val || '' })}
            />
            <div>
              <label className="text-xs font-semibold text-slate-800">Supplemental O2</label>
              <select
                value={form.o2Value}
                onChange={(e) =>
                  setForm({ ...form, o2Value: e.target.value as 'yes' | 'no' | 'unknown' })
                }
                className="mt-1.5 h-10 w-full rounded-xl border border-[#d9e8e6] bg-white px-3 text-xs font-medium text-slate-900 focus:border-teal-600 focus:outline-none"
              >
                <option value="no">Room Air (No)</option>
                <option value="yes">On Supplemental O2 (+2 pts)</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
          </div>

          {/* Consciousness */}
          <div className="pt-2">
            <label className="text-xs font-semibold text-slate-800">
              Consciousness Level (AVPU+C)
            </label>
            <select
              value={form.consciousnessValue}
              onChange={(e) =>
                setForm({ ...form, consciousnessValue: e.target.value as Consciousness })
              }
              className="mt-1.5 h-10 w-full rounded-xl border border-[#d9e8e6] bg-white px-3 text-xs font-medium text-slate-900 focus:border-teal-600 focus:outline-none"
            >
              <option value="A">Alert (A) - Fully oriented, normal (0 points)</option>
              <option value="C">New Confusion (C) - Acute altered mental state (3 points - Critical)</option>
              <option value="V">Voice Responsive (V) - Responds to verbal stimulus (3 points - Critical)</option>
              <option value="P">Pain Responsive (P) - Responds only to painful stimulus (3 points - Critical)</option>
              <option value="U">Unresponsive (U) - Glasgow Coma Scale depressed (3 points - Critical)</option>
            </select>
          </div>
        </div>
      </div>

      {/* CARD 3: HOME MEDICATIONS & ALLERGIES */}
      <div className="rounded-2xl border border-[#d9e8e6] bg-white p-5 sm:p-6 shadow-soft">
        <div className="flex items-center justify-between border-b border-[#d9e8e6] pb-3 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 text-teal-700">
              <Pill className="h-4 w-4" />
            </div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              3. Home Medications &amp; Documented Allergies
            </h3>
          </div>
          <span className="text-[11px] font-mono text-slate-500">
            {form.medications.length} meds &bull; {form.allergies.length} allergies
          </span>
        </div>

        {/* Medication History */}
        <div className="flex flex-col gap-3 mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span className="text-xs font-semibold text-slate-800">Current Medications</span>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-500">History Status:</span>
              <select
                value={form.medicationStatus}
                onChange={(e) =>
                  setForm({ ...form, medicationStatus: e.target.value as HistoryStatus })
                }
                className="h-8 rounded-lg border border-[#d9e8e6] bg-white px-2.5 text-[11px] font-mono text-slate-800 focus:border-teal-600 focus:outline-none"
              >
                <option value="confirmed_list">Confirmed List</option>
                <option value="confirmed_none">Confirmed None (No Meds)</option>
                <option value="incomplete">Incomplete History</option>
                <option value="unknown_unobtainable">Unknown / Unobtainable</option>
              </select>
            </div>
          </div>

          {/* Active Meds List */}
          <div className="flex flex-wrap gap-2 min-h-[44px] items-center p-3 rounded-xl bg-slate-50 border border-slate-200">
            {form.medications.length === 0 ? (
              <span className="text-xs text-slate-400 italic">
                No active home medications recorded.
              </span>
            ) : (
              form.medications.map((m, idx) => (
                <span
                  key={idx}
                  className="flex items-center gap-2 rounded-xl bg-white border border-teal-200 px-3 py-1.5 text-xs text-slate-900 font-mono shadow-soft-sm"
                >
                  <span className="font-bold text-teal-800">{m.raw_string}</span>
                  <span className="text-[10px] text-slate-500 flex items-center gap-0.5">
                    <Clock className="h-2.5 w-2.5 text-slate-400" />
                    {m.last_dose_hours_ago !== null ? `${m.last_dose_hours_ago}h ago` : 'Time unk'}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeMedication(idx)}
                    className="text-slate-400 hover:text-rose-600 transition-colors ml-1"
                    title="Remove medication"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </span>
              ))
            )}
          </div>

          {/* Add Medication Bar */}
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              list="formulary-suggestions"
              value={newMedName}
              onChange={(e) => setNewMedName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  addMedication(newMedName, newMedLastDose)
                }
              }}
              placeholder="Type drug name (e.g. Sildenafil, Metoprolol, Lisinopril, Nitroglycerin)..."
              className="h-10 flex-1 rounded-xl border border-[#d9e8e6] bg-white px-3 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-600 focus:outline-none"
            />
            <datalist id="formulary-suggestions">
              {COMMON_DRUGS.map((d) => (
                <option key={d} value={d} />
              ))}
            </datalist>

            <select
              value={newMedLastDose ?? 'unknown'}
              onChange={(e) =>
                setNewMedLastDose(e.target.value === 'unknown' ? null : Number(e.target.value))
              }
              className="h-10 rounded-xl border border-[#d9e8e6] bg-white px-3 text-xs text-slate-800 focus:border-teal-600 focus:outline-none font-mono"
            >
              <option value="12">Taken within 12h</option>
              <option value="24">Taken ~24h ago</option>
              <option value="36">Taken ~36h ago</option>
              <option value="48">Taken ~48h ago</option>
              <option value="72">Taken &gt;72h ago</option>
              <option value="unknown">Time Unknown</option>
            </select>

            <button
              type="button"
              onClick={() => addMedication(newMedName, newMedLastDose)}
              className="flex items-center justify-center gap-1.5 rounded-xl bg-teal-50 hover:bg-teal-100 border border-teal-200 px-4 h-10 text-xs font-bold text-teal-800 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add Med</span>
            </button>
          </div>
        </div>

        {/* Allergies History */}
        <div className="flex flex-col gap-3 pt-4 border-t border-[#d9e8e6]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-teal-600" />
              Documented Substance Allergies
            </span>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-500">Allergy Status:</span>
              <select
                value={form.allergyStatus}
                onChange={(e) =>
                  setForm({ ...form, allergyStatus: e.target.value as HistoryStatus })
                }
                className="h-8 rounded-lg border border-[#d9e8e6] bg-white px-2.5 text-[11px] font-mono text-slate-800 focus:border-teal-600 focus:outline-none"
              >
                <option value="confirmed_nkda">No Known Drug Allergies (NKDA)</option>
                <option value="confirmed_list">Confirmed Allergy List</option>
                <option value="unknown_unobtainable">Unknown / Unobtainable</option>
              </select>
            </div>
          </div>

          {/* Active Allergies List */}
          <div className="flex flex-wrap gap-2 min-h-[44px] items-center p-3 rounded-xl bg-slate-50 border border-slate-200">
            {form.allergies.length === 0 ? (
              <span className="text-xs text-slate-400 italic">
                {form.allergyStatus === 'confirmed_nkda'
                  ? 'No Known Drug Allergies (NKDA Confirmed).'
                  : 'No allergies recorded.'}
              </span>
            ) : (
              form.allergies.map((a, idx) => (
                <span
                  key={idx}
                  className="flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-300 px-3 py-1.5 text-xs text-amber-950 font-mono shadow-soft-sm"
                >
                  <span className="font-bold text-amber-900">{a.raw_substance}</span>
                  <span className="text-[10px] text-amber-700">({a.reaction_type})</span>
                  <button
                    type="button"
                    onClick={() => removeAllergy(idx)}
                    className="text-amber-500 hover:text-rose-600 transition-colors ml-1"
                    title="Remove allergy"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </span>
              ))
            )}
          </div>

          {/* Add Allergy Input Bar */}
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={newAllergySubstance}
              onChange={(e) => setNewAllergySubstance(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  addAllergy(newAllergySubstance, newAllergyReaction)
                }
              }}
              placeholder="Allergen name (e.g. Penicillin, Ceftriaxone, Amoxicillin)..."
              className="h-10 flex-1 rounded-xl border border-[#d9e8e6] bg-white px-3 text-xs text-slate-900 placeholder-slate-400 focus:border-teal-600 focus:outline-none"
            />
            <select
              value={newAllergyReaction}
              onChange={(e) => setNewAllergyReaction(e.target.value as ReactionType)}
              className="h-10 rounded-xl border border-[#d9e8e6] bg-white px-3 text-xs text-slate-800 focus:border-teal-600 focus:outline-none"
            >
              <option value="anaphylaxis_ige">IgE Anaphylaxis / Airway Compromise</option>
              <option value="severe_cutaneous_scar">Severe Cutaneous (SCAR / DRESS / SJS)</option>
              <option value="mild_rash">Mild Rash / Urticaria</option>
              <option value="gi_upset">GI Upset / Intolerance</option>
              <option value="unknown">Reaction Unknown</option>
            </select>
            <button
              type="button"
              onClick={() => addAllergy(newAllergySubstance, newAllergyReaction)}
              className="flex items-center justify-center gap-1.5 rounded-xl bg-amber-50 hover:bg-amber-100 border border-amber-200 px-4 h-10 text-xs font-bold text-amber-900 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add Allergy</span>
            </button>
          </div>
        </div>
      </div>

      {/* PRIMARY CTA: EVALUATE PATIENT */}
      <div className="sticky bottom-4 z-20 flex flex-col gap-3 rounded-2xl border border-teal-200 bg-white/95 p-4 sm:p-5 shadow-soft-xl backdrop-blur-md">
        {errorMessage && (
          <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
            <span className="font-semibold">{errorMessage}</span>
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <FileText className="h-4 w-4 text-teal-600" />
            <span>Ready for Pass 1 Deterministic Safety Evaluation</span>
          </div>

          <button
            type="submit"
            onClick={handleSubmit}
            disabled={isLoading}
            className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-teal-700 to-teal-800 hover:from-teal-800 hover:to-teal-900 px-7 py-3 text-sm font-bold text-white shadow-soft hover:shadow-soft-lg transition-all disabled:opacity-50 cursor-pointer"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-teal-200" />
                <span>Running Deterministic Engine...</span>
              </>
            ) : (
              <>
                <span>Evaluate Patient &amp; View Report</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </form>
  )
}

export default PatientIntakeForm
