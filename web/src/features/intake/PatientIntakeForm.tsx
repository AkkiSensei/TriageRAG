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

  medicationStatus: 'confirmed_list',
  medications: [{ raw_string: 'Sildenafil 50mg', last_dose_hours_ago: 12 }],

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
}

export const PatientIntakeForm: React.FC<PatientIntakeFormProps> = ({
  onSubmit,
  isLoading,
  initialScenario,
  existingRequest,
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

      medicationStatus: p.medication_history_status as HistoryStatus,
      medications: p.medications
        ? p.medications.map((m) => {
            let hoursAgo: number | null = 12
            if (m.last_dose_time) {
              const diff = Date.now() - new Date(m.last_dose_time).getTime()
              hoursAgo = Math.max(1, Math.round(diff / (3600 * 1000)))
            }
            return { raw_string: m.raw_text, last_dose_hours_ago: hoursAgo }
          })
        : [],

      allergyStatus: p.allergy_history_status as HistoryStatus,
      allergies: p.allergies
        ? p.allergies.map((a) => ({
            raw_substance: a.raw_substance,
            reaction_type: (a.reaction_type as ReactionType) || 'unknown',
          }))
        : [],

      suspectedSyndrome: p.suspected_syndrome || '',
      renalImpairment: (p.renal_impairment as Impairment) || 'unknown',
      hepaticImpairment: (p.hepatic_impairment as Impairment) || 'unknown',

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

      medicationStatus: p.medication_history_status as HistoryStatus,
      medications: p.medications
        ? p.medications.map((m) => {
            let hoursAgo: number | null = 12
            if (m.last_dose_time) {
              const diff = Date.now() - new Date(m.last_dose_time).getTime()
              hoursAgo = Math.max(1, Math.round(diff / (3600 * 1000)))
            }
            return { raw_string: m.raw_text, last_dose_hours_ago: hoursAgo }
          })
        : [],

      allergyStatus: p.allergy_history_status as HistoryStatus,
      allergies: p.allergies
        ? p.allergies.map((a) => ({
            raw_substance: a.raw_substance,
            reaction_type: (a.reaction_type as ReactionType) || 'unknown',
          }))
        : [],

      suspectedSyndrome: p.suspected_syndrome || '',
      renalImpairment: (p.renal_impairment as Impairment) || 'unknown',
      hepaticImpairment: (p.hepatic_impairment as Impairment) || 'unknown',

      chiefComplaint: p.chief_complaint_untrusted || '',
      includeComplaintInLlm: req.include_complaint_in_llm ?? false,
      llmProfile: req.llm_profile ?? 'COMPLIANT',
    })
  }

  const buildApiPayload = (): TriageApiRequest => {
    const assessedAt = new Date().toISOString()
    const assessedMs = new Date(assessedAt).getTime()

    return {
      patient: {
        assessed_at: assessedAt,
        age: {
          value: form.ageValue,
          unit: form.ageUnit,
        },
        sex: form.sex,
        pregnancy: form.sex === 'male' ? 'no' : form.pregnancy,
        weight_kg: {
          value: form.weightStatus === 'unknown' ? null : form.weightValue,
          source: form.weightStatus,
        },
        vitals: {
          heart_rate_bpm: {
            value: form.hrStatus === 'unknown' ? null : form.hrValue,
            source: form.hrStatus,
          },
          systolic_bp_mmhg: {
            value: form.sbpStatus === 'unknown' ? null : form.sbpValue,
            source: form.sbpStatus,
          },
          diastolic_bp_mmhg: {
            value: form.dbpStatus === 'unknown' ? null : form.dbpValue,
            source: form.dbpStatus,
          },
          respiratory_rate_bpm: {
            value: form.rrStatus === 'unknown' ? null : form.rrValue,
            source: form.rrStatus,
          },
          spo2_percent: {
            value: form.spo2Status === 'unknown' ? null : form.spo2Value,
            source: form.spo2Status,
          },
          supplemental_o2: {
            value: form.o2Status === 'unknown' ? null : form.o2Value,
            source: form.o2Status,
          },
          temperature_c: {
            value: form.tempStatus === 'unknown' ? null : form.tempValue,
            source: form.tempStatus,
          },
          blood_glucose_mg_dl: {
            value: form.glucoseStatus === 'unknown' ? null : form.glucoseValue,
            source: form.glucoseStatus,
          },
          consciousness: {
            value: form.consciousnessStatus === 'unknown' ? null : form.consciousnessValue,
            source: form.consciousnessStatus,
          },
        },
        medication_history_status: form.medicationStatus,
        medications: form.medications.map((m) => {
          let lastDoseIso: string | null = null
          if (m.last_dose_hours_ago !== null && m.last_dose_hours_ago !== undefined) {
            const timeAgo = new Date(assessedMs - m.last_dose_hours_ago * 3600 * 1000)
            lastDoseIso = timeAgo.toISOString()
          }
          return {
            raw_text: m.raw_string,
            last_dose_time: lastDoseIso,
          }
        }),
        allergy_history_status: form.allergyStatus,
        allergies: form.allergies.map((a) => ({
          raw_substance: a.raw_substance,
          reaction_type: a.reaction_type,
        })),
        suspected_syndrome: form.suspectedSyndrome || null,
        renal_impairment: form.renalImpairment,
        hepatic_impairment: form.hepaticImpairment,
        chief_complaint_untrusted: form.chiefComplaint,
      },
      llm_profile: form.llmProfile,
      include_complaint_in_llm: form.includeComplaintInLlm,
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
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {/* CARD 1: PRESENTING SYNDROME & CLINICAL NARRATIVE */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-teal-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              1. Presenting Clinical Syndrome & Narrative
            </h3>
          </div>
          <button
            type="button"
            onClick={() => setForm(INITIAL_FORM_STATE)}
            className="flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-slate-200 transition-colors"
            title="Reset to default baseline"
          >
            <RotateCcw className="h-3 w-3" />
            <span>Reset</span>
          </button>
        </div>

        <div className="flex flex-col gap-3.5">
          {/* Syndrome Dropdown */}
          <div>
            <label className="text-xs font-medium text-slate-300 flex items-center justify-between">
              <span>Suspected Clinical Syndrome</span>
              <span className="text-[10px] text-teal-400 font-mono">Guides Protocol Retrieval</span>
            </label>
            <select
              value={form.suspectedSyndrome}
              onChange={(e) => setForm({ ...form, suspectedSyndrome: e.target.value })}
              className="mt-1 h-9 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-xs text-slate-100 focus:border-teal-500 focus:outline-none"
            >
              <option value="">None / Unspecified (General Vitals Screening)</option>
              <option value="chest_pain">Acute Chest Pain & Suspected Coronary Syndrome</option>
              <option value="anaphylaxis">Acute Anaphylaxis / Severe Systemic Allergic Reaction</option>
              <option value="severe_asthma">Severe Acute Asthma & Bronchospasm</option>
              <option value="hypoglycemia">Acute Symptomatic Hypoglycemia</option>
              <option value="paediatric_sepsis">Pediatric Sepsis & Febrile Shock</option>
              <option value="altered_mental_status">Altered Mental Status / Acute Confusion</option>
            </select>
          </div>

          {/* Chief Complaint / Triage Narrative */}
          <div>
            <label className="text-xs font-medium text-slate-300 flex items-center justify-between">
              <span>Clinical Notes / Triage Narrative</span>
              <span className="text-[10px] text-slate-400 font-mono">
                Patient-reported • Quarantined from decision engine
              </span>
            </label>
            <textarea
              rows={2}
              value={form.chiefComplaint}
              onChange={(e) => setForm({ ...form, chiefComplaint: e.target.value })}
              placeholder="Enter patient-reported narrative or paramedic handoff notes..."
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 p-2.5 text-xs text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none resize-none font-sans leading-relaxed"
            />
          </div>
        </div>
      </div>

      {/* CARD 2: DEMOGRAPHICS & PHYSIOLOGICAL VITALS */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Stethoscope className="h-4 w-4 text-teal-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              2. Demographics & Physiological Vitals
            </h3>
          </div>
          <span className="text-[10px] font-mono text-slate-400">NEWS2 Standard</span>
        </div>

        {/* Demographics Row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          {/* Age */}
          <div>
            <label className="text-[11px] font-medium text-slate-300">Age</label>
            <div className="mt-1 flex gap-1.5">
              <input
                type="text"
                value={form.ageValue}
                onChange={(e) => setForm({ ...form, ageValue: e.target.value })}
                placeholder="62"
                className="h-8.5 w-2/3 rounded-md border border-slate-800 bg-slate-950 px-2.5 text-xs text-slate-100 focus:border-teal-500 focus:outline-none"
              />
              <select
                value={form.ageUnit}
                onChange={(e) => setForm({ ...form, ageUnit: e.target.value as AgeUnit })}
                className="h-8.5 w-1/3 rounded-md border border-slate-800 bg-slate-950 px-1 text-[11px] text-slate-300 focus:border-teal-500 focus:outline-none"
              >
                <option value="years">yr</option>
                <option value="months">mo</option>
                <option value="days">d</option>
              </select>
            </div>
          </div>

          {/* Biological Sex */}
          <div>
            <label className="text-[11px] font-medium text-slate-300">Biological Sex</label>
            <select
              value={form.sex}
              onChange={(e) => handleSexChange(e.target.value as Sex)}
              className="mt-1 h-8.5 w-full rounded-md border border-slate-800 bg-slate-950 px-2 text-xs text-slate-300 focus:border-teal-500 focus:outline-none"
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
              <label className="text-[11px] font-medium text-slate-300">Pregnancy</label>
              {form.sex === 'male' && (
                <span className="text-[10px] text-slate-400 font-mono">Auto-Locked</span>
              )}
            </div>
            {form.sex === 'male' ? (
              <div
                className="mt-1 flex h-8.5 w-full items-center rounded-md border border-slate-800 bg-slate-950/60 px-2.5 text-xs text-slate-400 font-mono cursor-not-allowed select-none"
                title="Biological invariant: Male patients are not pregnant"
              >
                No (N/A)
              </div>
            ) : (
              <select
                value={form.pregnancy}
                onChange={(e) => setForm({ ...form, pregnancy: e.target.value as Pregnancy })}
                className="mt-1 h-8.5 w-full rounded-md border border-teal-500/30 bg-slate-950 px-2 text-xs text-slate-200 focus:border-teal-500 focus:outline-none"
              >
                <option value="no">Not Pregnant (No)</option>
                <option value="yes">Pregnant (Yes)</option>
                <option value="unknown">Unknown</option>
              </select>
            )}
          </div>

          {/* Weight */}
          <div>
            <label className="text-[11px] font-medium text-slate-300">Weight (kg)</label>
            <input
              type="text"
              value={form.weightValue}
              onChange={(e) => setForm({ ...form, weightValue: e.target.value })}
              placeholder="82.0"
              className="mt-1 h-8.5 w-full rounded-md border border-slate-800 bg-slate-950 px-2.5 text-xs text-slate-100 focus:border-teal-500 focus:outline-none"
            />
          </div>
        </div>

        {/* 7 Physiological Vitals Grid */}
        <div className="flex flex-col gap-2 pt-3 border-t border-slate-800/60">
          <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
            Physiological Measurements
          </span>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
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
              <label className="text-[11px] font-medium text-slate-300">Supplemental O2</label>
              <select
                value={form.o2Value}
                onChange={(e) =>
                  setForm({ ...form, o2Value: e.target.value as 'yes' | 'no' | 'unknown' })
                }
                className="mt-1 h-8.5 w-full rounded-md border border-slate-800 bg-slate-950 px-2 text-xs text-slate-200 focus:border-teal-500 focus:outline-none"
              >
                <option value="no">Room Air (No)</option>
                <option value="yes">On Supplemental O2 (+2 pts)</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
          </div>

          {/* Consciousness */}
          <div className="pt-2">
            <label className="text-[11px] font-medium text-slate-300">
              Consciousness Level (AVPU+C)
            </label>
            <select
              value={form.consciousnessValue}
              onChange={(e) =>
                setForm({ ...form, consciousnessValue: e.target.value as Consciousness })
              }
              className="mt-1 h-8.5 w-full rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-200 focus:border-teal-500 focus:outline-none"
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
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Pill className="h-4 w-4 text-teal-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              3. Home Medications & Documented Allergies
            </h3>
          </div>
          <span className="text-[10px] font-mono text-slate-400">
            {form.medications.length} meds • {form.allergies.length} allergies
          </span>
        </div>

        {/* Medication History */}
        <div className="flex flex-col gap-3 mb-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span className="text-xs font-semibold text-slate-300">Current Medications</span>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-400">History Status:</span>
              <select
                value={form.medicationStatus}
                onChange={(e) =>
                  setForm({ ...form, medicationStatus: e.target.value as HistoryStatus })
                }
                className="h-7 rounded border border-slate-800 bg-slate-950 px-2 text-[11px] text-slate-300 focus:border-teal-500 focus:outline-none font-mono"
              >
                <option value="confirmed_list">Confirmed List</option>
                <option value="confirmed_none">Confirmed None (No Meds)</option>
                <option value="incomplete">Incomplete History</option>
                <option value="unknown_unobtainable">Unknown / Unobtainable</option>
              </select>
            </div>
          </div>

          {/* Active Meds List */}
          <div className="flex flex-wrap gap-2 min-h-[40px] items-center p-2.5 rounded-lg bg-slate-950 border border-slate-800/80">
            {form.medications.length === 0 ? (
              <span className="text-xs text-slate-400 italic">
                No active home medications recorded.
              </span>
            ) : (
              form.medications.map((m, idx) => (
                <span
                  key={idx}
                  className="flex items-center gap-2 rounded bg-slate-900 border border-slate-700 px-2.5 py-1 text-xs text-slate-200 font-mono shadow-sm"
                >
                  <span className="font-semibold text-teal-300">{m.raw_string}</span>
                  <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                    <Clock className="h-2.5 w-2.5" />
                    {m.last_dose_hours_ago !== null ? `${m.last_dose_hours_ago}h ago` : 'Time unk'}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeMedication(idx)}
                    className="text-slate-500 hover:text-red-400 transition-colors ml-1"
                    title="Remove medication"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </span>
              ))
            )}
          </div>

          {/* Add Medication Input Bar with Autocomplete & Last Taken Window */}
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
              placeholder="Select or type medication (e.g. Sildenafil 50mg, Metoprolol)..."
              className="h-8.5 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 text-xs text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none"
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
              className="h-8.5 rounded-md border border-slate-700 bg-slate-950 px-2 text-xs text-slate-300 focus:border-teal-500 focus:outline-none font-mono"
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
              className="flex items-center justify-center gap-1.5 rounded-md bg-slate-800 hover:bg-slate-700 px-3.5 h-8.5 text-xs font-medium text-slate-200 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add Med</span>
            </button>
          </div>
        </div>

        {/* Allergies History */}
        <div className="flex flex-col gap-3 pt-3 border-t border-slate-800/60">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-teal-400" />
              Documented Substance Allergies
            </span>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-400">Allergy Status:</span>
              <select
                value={form.allergyStatus}
                onChange={(e) =>
                  setForm({ ...form, allergyStatus: e.target.value as HistoryStatus })
                }
                className="h-7 rounded border border-slate-800 bg-slate-950 px-2 text-[11px] text-slate-300 focus:border-teal-500 focus:outline-none font-mono"
              >
                <option value="confirmed_nkda">No Known Drug Allergies (NKDA)</option>
                <option value="confirmed_list">Confirmed Allergy List</option>
                <option value="unknown_unobtainable">Unknown / Unobtainable</option>
              </select>
            </div>
          </div>

          {/* Active Allergies List */}
          <div className="flex flex-wrap gap-2 min-h-[40px] items-center p-2.5 rounded-lg bg-slate-950 border border-slate-800/80">
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
                  className="flex items-center gap-2 rounded bg-amber-950/40 border border-amber-800/60 px-2.5 py-1 text-xs text-amber-200 font-mono shadow-sm"
                >
                  <span className="font-bold text-amber-300">{a.raw_substance}</span>
                  <span className="text-[10px] text-amber-400/80">({a.reaction_type})</span>
                  <button
                    type="button"
                    onClick={() => removeAllergy(idx)}
                    className="text-amber-400 hover:text-red-400 transition-colors ml-1"
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
              placeholder="Allergen name (e.g. Penicillin, Cephalosporins, Amoxicillin)..."
              className="h-8.5 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 text-xs text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none"
            />
            <select
              value={newAllergyReaction}
              onChange={(e) => setNewAllergyReaction(e.target.value as ReactionType)}
              className="h-8.5 rounded-md border border-slate-700 bg-slate-950 px-2 text-xs text-slate-300 focus:border-teal-500 focus:outline-none"
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
              className="flex items-center justify-center gap-1.5 rounded-md bg-slate-800 hover:bg-slate-700 px-3.5 h-8.5 text-xs font-medium text-slate-200 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Add Allergy</span>
            </button>
          </div>
        </div>
      </div>

      {/* PRIMARY CTA: EVALUATE PATIENT */}
      <div className="sticky bottom-4 z-20 flex items-center justify-between rounded-xl border border-teal-500/40 bg-slate-950/95 p-4 shadow-2xl backdrop-blur-md">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <FileText className="h-4 w-4 text-teal-400" />
          <span>Form ready for deterministic safety verification</span>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="flex items-center gap-2 rounded-lg bg-teal-500 hover:bg-teal-400 px-6 py-2.5 text-sm font-bold text-slate-950 shadow-lg shadow-teal-500/20 transition-all disabled:opacity-50"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Evaluating Patient...</span>
            </>
          ) : (
            <>
              <span>Evaluate Patient & Generate Report</span>
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </div>
    </form>
  )
}
export default PatientIntakeForm
