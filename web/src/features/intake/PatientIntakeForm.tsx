import React, { useState } from 'react'
import { MeasuredInput, type MeasurementStatus } from './MeasuredInput'
import type { TriageApiRequest, ScenarioDetail } from '@/lib/api'
import type { components } from '@/types/api'
import {
  Plus,
  Trash2,
  Play,
  RotateCcw,
  Heart,
  Stethoscope,
  Pill,
  ShieldCheck,
  Eye,
  SlidersHorizontal,
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

interface PatientIntakeFormProps {
  onSubmit: (request: TriageApiRequest) => void
  isLoading?: boolean
  initialScenario?: ScenarioDetail | null
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
  medications: Array<{ raw_string: string; dose?: string; unit?: string; route?: string }>

  // Allergy history
  allergyStatus: HistoryStatus
  allergies: Array<{
    raw_substance: string
    reaction_type: ReactionType
  }>

  // Clinical context
  suspectedSyndrome: string
  renalImpairment: Impairment
  hepaticImpairment: Impairment

  // Untrusted chief complaint
  chiefComplaint: string
  includeComplaintInLlm: boolean
  llmProfile: LLMProfile
}

export const INITIAL_FORM_STATE: FormState = {
  ageValue: '62',
  ageUnit: 'years',
  sex: 'male',
  // Rule: By default NO for a male (obvious biological invariant)
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
  medications: [{ raw_string: 'Sildenafil 50mg daily' }],

  allergyStatus: 'confirmed_nkda',
  allergies: [],

  suspectedSyndrome: 'chest_pain',
  renalImpairment: 'no',
  hepaticImpairment: 'no',

  chiefComplaint: 'Patient presents with severe retrosternal chest pain radiating to left arm.',
  includeComplaintInLlm: false,
  llmProfile: 'COMPLIANT',
}

export const PatientIntakeForm: React.FC<PatientIntakeFormProps> = ({
  onSubmit,
  isLoading,
  initialScenario,
}) => {
  const [form, setForm] = useState<FormState>(INITIAL_FORM_STATE)
  const [activeTab, setActiveTab] = useState<'patient' | 'meds'>('patient')
  const [showAllInOne, setShowAllInOne] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Medication and allergy quick add text
  const [newMedText, setNewMedText] = useState('')
  const [newAllergySubstance, setNewAllergySubstance] = useState('')
  const [newAllergyReaction, setNewAllergyReaction] = useState<ReactionType>('anaphylaxis_ige')

  // Handle sex change: automatically enforce pregnancy invariant
  const handleSexChange = (newSex: Sex) => {
    setForm((prev) => ({
      ...prev,
      sex: newSex,
      // Invariant: pregnancy is strictly 'no' for male
      pregnancy: newSex === 'male' ? 'no' : prev.pregnancy,
    }))
  }

  // Populate from scenario
  React.useEffect(() => {
    if (initialScenario) {
      loadScenarioState(initialScenario)
    }
  }, [initialScenario])

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
      // Invariant: If male, pregnancy is strictly 'no'
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
      medications: p.medications ? p.medications.map((m) => ({ raw_string: m.raw_text })) : [],

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

  const buildApiPayload = (): TriageApiRequest => {
    return {
      patient: {
        assessed_at: new Date().toISOString(),
        age: {
          value: form.ageValue,
          unit: form.ageUnit,
        },
        sex: form.sex,
        // Enforce male pregnancy invariant at payload serialization
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
        medications: form.medications.map((m) => ({ raw_text: m.raw_string })),
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

  // Quick preset actions
  const addMedication = (text: string) => {
    if (!text.trim()) return
    setForm((prev) => ({
      ...prev,
      medications: [...prev.medications, { raw_string: text.trim() }],
      medicationStatus: 'confirmed_list',
    }))
    setNewMedText('')
  }

  const removeMedication = (index: number) => {
    setForm((prev) => {
      const updated = prev.medications.filter((_, i) => i !== index)
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

  const removeAllergy = (index: number) => {
    setForm((prev) => {
      const updated = prev.allergies.filter((_, i) => i !== index)
      return {
        ...prev,
        allergies: updated,
        allergyStatus: updated.length === 0 ? 'confirmed_nkda' : 'confirmed_list',
      }
    })
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {/* Debloated View Mode Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
        {!showAllInOne ? (
          <div className="flex rounded-lg bg-slate-900 border border-slate-800 p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab('patient')}
              className={`flex items-center gap-1.5 py-1.5 px-3 rounded-md font-medium transition-all ${
                activeTab === 'patient'
                  ? 'bg-teal-500/20 text-teal-300 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Heart className="h-3.5 w-3.5" />
              <span>1. Patient & Vitals</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('meds')}
              className={`flex items-center gap-1.5 py-1.5 px-3 rounded-md font-medium transition-all ${
                activeTab === 'meds'
                  ? 'bg-teal-500/20 text-teal-300 font-semibold shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Pill className="h-3.5 w-3.5" />
              <span>
                2. Meds & Allergies ({form.medications.length + form.allergies.length})
              </span>
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
            <Stethoscope className="h-4 w-4 text-teal-400" />
            <span>Complete Intake Record</span>
          </div>
        )}

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowAllInOne(!showAllInOne)}
            className="flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-teal-300 transition-colors"
          >
            <Eye className="h-3.5 w-3.5" />
            <span>{showAllInOne ? 'Tabbed View' : 'All-in-One'}</span>
          </button>
          <button
            type="button"
            onClick={() => setForm(INITIAL_FORM_STATE)}
            title="Reset to default patient"
            className="rounded p-1 text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* SECTION 1: PATIENT DEMOGRAPHICS & VITALS */}
      {(showAllInOne || activeTab === 'patient') && (
        <div className="flex flex-col gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
              <Stethoscope className="h-3.5 w-3.5 text-teal-400" />
              Demographics & Physical Profile
            </span>
            <span className="text-[10px] font-mono text-slate-400">NEWS2 Standard</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
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

            {/* Sex */}
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

            {/* Pregnancy Status (LOCKED to No for Male) */}
            <div>
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-medium text-slate-300">Pregnancy</label>
                {form.sex === 'male' && (
                  <span className="text-[10px] text-slate-400 font-mono">Male</span>
                )}
              </div>
              {form.sex === 'male' ? (
                <div
                  className="mt-1 flex h-8.5 w-full items-center rounded-md border border-slate-800 bg-slate-950/60 px-2.5 text-xs text-slate-400 font-mono cursor-not-allowed select-none"
                  title="Pregnancy status is automatically No for male patients"
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

          {/* Vitals Grid (Debloated & Responsive) */}
          <div className="flex flex-col gap-2 pt-2 border-t border-slate-800/60">
            <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
              Physiological Vitals
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
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
                label="Oxygen (SpO2)"
                unit="%"
                type="number"
                status={form.spo2Status}
                value={form.spo2Value}
                placeholder="98"
                onStatusChange={(status) => setForm({ ...form, spo2Status: status })}
                onValueChange={(val) => setForm({ ...form, spo2Value: val })}
              />
              <MeasuredInput
                label="Temp"
                unit="°C"
                status={form.tempStatus}
                value={form.tempValue}
                placeholder="37.1"
                onStatusChange={(status) => setForm({ ...form, tempStatus: status })}
                onValueChange={(val) => setForm({ ...form, tempValue: val || '' })}
              />
            </div>

            {/* Consciousness & Supplemental O2 Row */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              <div>
                <label className="text-[11px] font-medium text-slate-300">
                  Consciousness (AVPU+C)
                </label>
                <select
                  value={form.consciousnessValue}
                  onChange={(e) =>
                    setForm({ ...form, consciousnessValue: e.target.value as Consciousness })
                  }
                  className="mt-1 h-8.5 w-full rounded-md border border-slate-800 bg-slate-950 px-2 text-xs text-slate-200 focus:border-teal-500 focus:outline-none"
                >
                  <option value="A">Alert (A) - Normal (0 pts)</option>
                  <option value="C">New Confusion (C) - Critical (3 pts)</option>
                  <option value="V">Voice Responsive (V) - Critical (3 pts)</option>
                  <option value="P">Pain Responsive (P) - Critical (3 pts)</option>
                  <option value="U">Unresponsive (U) - Critical (3 pts)</option>
                </select>
              </div>

              <div>
                <label className="text-[11px] font-medium text-slate-300">
                  Supplemental O2
                </label>
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
          </div>
        </div>
      )}

      {/* SECTION 2: MEDICATIONS, ALLERGIES & CHIEF COMPLAINT */}
      {(showAllInOne || activeTab === 'meds') && (
        <div className="flex flex-col gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          {/* Active Medications */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-1.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
                <Pill className="h-3.5 w-3.5 text-teal-400" />
                Current Medications
              </span>
              <span className="text-[10px] font-mono text-slate-400">
                {form.medications.length} active
              </span>
            </div>

            {/* Quick Add Presets */}
            <div className="flex flex-wrap gap-1.5">
              <span className="text-[10px] text-slate-400 self-center">Quick Add:</span>
              <button
                type="button"
                onClick={() => addMedication('Sildenafil 50mg daily')}
                className="rounded-full bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[10px] text-slate-200 border border-slate-700 transition-colors"
              >
                + Sildenafil 50mg
              </button>
              <button
                type="button"
                onClick={() => addMedication('Metoprolol 25mg daily')}
                className="rounded-full bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[10px] text-slate-200 border border-slate-700 transition-colors"
              >
                + Metoprolol 25mg
              </button>
              <button
                type="button"
                onClick={() => addMedication('Lisinopril 10mg daily')}
                className="rounded-full bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[10px] text-slate-200 border border-slate-700 transition-colors"
              >
                + Lisinopril 10mg
              </button>
              <button
                type="button"
                onClick={() => addMedication('Nitroglycerin 0.4mg sublingual')}
                className="rounded-full bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[10px] text-slate-200 border border-slate-700 transition-colors"
              >
                + Nitroglycerin
              </button>
            </div>

            {/* Existing Meds List */}
            <div className="flex flex-wrap gap-2 min-h-[36px] items-center p-2 rounded-lg bg-slate-950 border border-slate-800/80">
              {form.medications.length === 0 ? (
                <span className="text-xs text-slate-400 italic">
                  No current medications documented (Confirmed None).
                </span>
              ) : (
                form.medications.map((m, idx) => (
                  <span
                    key={idx}
                    className="flex items-center gap-1.5 rounded bg-slate-900 border border-slate-700 px-2 py-1 text-xs text-slate-200 font-mono shadow-sm"
                  >
                    <span>{m.raw_string}</span>
                    <button
                      type="button"
                      onClick={() => removeMedication(idx)}
                      className="text-slate-400 hover:text-red-400"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </span>
                ))
              )}
            </div>

            {/* Custom Med Input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={newMedText}
                onChange={(e) => setNewMedText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addMedication(newMedText)
                  }
                }}
                placeholder="Type custom medication name & dose, then click Add..."
                className="h-8.5 flex-1 rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => addMedication(newMedText)}
                className="flex items-center gap-1 rounded-md bg-slate-800 hover:bg-slate-700 px-3 text-xs font-medium text-slate-200 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" /> Add
              </button>
            </div>
          </div>

          {/* Allergies */}
          <div className="flex flex-col gap-2 pt-2 border-t border-slate-800/60">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-1.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
                <ShieldCheck className="h-3.5 w-3.5 text-teal-400" />
                Documented Allergies
              </span>
              <span className="text-[10px] font-mono text-slate-400">
                {form.allergies.length} recorded
              </span>
            </div>

            {/* Quick Allergy Presets */}
            <div className="flex flex-wrap gap-1.5">
              <span className="text-[10px] text-slate-400 self-center">Quick Add:</span>
              <button
                type="button"
                onClick={() => addAllergy('Penicillin', 'anaphylaxis_ige')}
                className="rounded-full bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[10px] text-amber-300 border border-amber-800/50 transition-colors"
              >
                + Penicillin (Anaphylaxis)
              </button>
              <button
                type="button"
                onClick={() => addAllergy('Amoxicillin', 'anaphylaxis_ige')}
                className="rounded-full bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[10px] text-amber-300 border border-amber-800/50 transition-colors"
              >
                + Amoxicillin (Anaphylaxis)
              </button>
              <button
                type="button"
                onClick={() => addAllergy('Cephalosporin', 'mild_rash')}
                className="rounded-full bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[10px] text-slate-300 border border-slate-700 transition-colors"
              >
                + Cephalosporin (Rash)
              </button>
              <button
                type="button"
                onClick={() =>
                  setForm((p) => ({
                    ...p,
                    allergies: [],
                    allergyStatus: 'confirmed_nkda',
                  }))
                }
                className="rounded-full bg-teal-950/60 hover:bg-teal-900/60 px-2 py-0.5 text-[10px] text-teal-300 border border-teal-800/50 transition-colors"
              >
                ✓ Set NKDA (No Known Allergies)
              </button>
            </div>

            {/* Existing Allergies List */}
            <div className="flex flex-wrap gap-2 min-h-[36px] items-center p-2 rounded-lg bg-slate-950 border border-slate-800/80">
              {form.allergies.length === 0 ? (
                <span className="text-xs text-slate-400 italic font-mono">
                  No Known Drug Allergies (NKDA).
                </span>
              ) : (
                form.allergies.map((a, idx) => (
                  <span
                    key={idx}
                    className="flex items-center gap-1.5 rounded bg-amber-950/60 border border-amber-800/80 px-2 py-1 text-xs text-amber-200 font-mono shadow-sm"
                  >
                    <span>
                      {a.raw_substance} ({a.reaction_type})
                    </span>
                    <button
                      type="button"
                      onClick={() => removeAllergy(idx)}
                      className="text-amber-400 hover:text-red-400"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </span>
                ))
              )}
            </div>

            {/* Custom Allergy Input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={newAllergySubstance}
                onChange={(e) => setNewAllergySubstance(e.target.value)}
                placeholder="Substance (e.g. Aspirin)..."
                className="h-8.5 w-1/2 rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none"
              />
              <select
                value={newAllergyReaction}
                onChange={(e) => setNewAllergyReaction(e.target.value as ReactionType)}
                className="h-8.5 w-1/3 rounded-md border border-slate-800 bg-slate-950 px-2 text-xs text-slate-300 focus:border-teal-500 focus:outline-none"
              >
                <option value="anaphylaxis_ige">Anaphylaxis (IgE)</option>
                <option value="severe_cutaneous_scar">Severe Cutaneous (SCAR)</option>
                <option value="mild_rash">Mild Rash</option>
                <option value="gi_upset">GI Upset</option>
                <option value="unknown">Unknown</option>
              </select>
              <button
                type="button"
                onClick={() => addAllergy(newAllergySubstance, newAllergyReaction)}
                className="flex items-center gap-1 rounded-md bg-slate-800 hover:bg-slate-700 px-3 text-xs font-medium text-slate-200 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" /> Add
              </button>
            </div>
          </div>

          {/* Chief Complaint (Quarantined) */}
          <div className="flex flex-col gap-1.5 pt-2 border-t border-slate-800/60">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-medium text-slate-300 flex items-center gap-1.5">
                <span>Free-Text Chief Complaint</span>
                <span className="text-[10px] text-amber-400 font-mono bg-amber-950/60 px-1.5 py-0.2 rounded border border-amber-900/60">
                  Rule R7: Quarantined
                </span>
              </label>
              <span className="text-[10px] text-slate-400">
                Never touches engine decision logic
              </span>
            </div>
            <textarea
              rows={2}
              value={form.chiefComplaint}
              onChange={(e) => setForm({ ...form, chiefComplaint: e.target.value })}
              placeholder="Enter patient narrative complaint..."
              className="w-full rounded-md border border-slate-800 bg-slate-950 p-2 text-xs text-slate-200 placeholder-slate-600 focus:border-teal-500 focus:outline-none resize-none font-sans"
            />
          </div>
        </div>
      )}

      {/* Advanced / Simulation Drawer Toggle */}
      <div className="flex items-center justify-between text-xs text-slate-400 px-1">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-slate-200 transition-colors"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" />
          <span>{showAdvanced ? 'Hide Advanced Options' : 'Advanced Clinical Settings'}</span>
        </button>
        <span className="text-[10px] font-mono text-slate-400">Press Ctrl+Enter to Run</span>
      </div>

      {showAdvanced && (
        <div className="flex flex-col gap-3 rounded-xl border border-slate-800/80 bg-slate-950/80 p-3.5 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-medium text-slate-300">Renal Impairment</label>
              <select
                value={form.renalImpairment}
                onChange={(e) => setForm({ ...form, renalImpairment: e.target.value as Impairment })}
                className="mt-1 h-8 w-full rounded border border-slate-800 bg-slate-900 px-2 text-xs text-slate-300"
              >
                <option value="no">None (Normal)</option>
                <option value="yes">Impaired (CrCl &lt; 30)</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] font-medium text-slate-300">Hepatic Impairment</label>
              <select
                value={form.hepaticImpairment}
                onChange={(e) =>
                  setForm({ ...form, hepaticImpairment: e.target.value as Impairment })
                }
                className="mt-1 h-8 w-full rounded border border-slate-800 bg-slate-900 px-2 text-xs text-slate-300"
              >
                <option value="no">None (Normal)</option>
                <option value="yes">Impaired (Child-Pugh B/C)</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Primary Action Button */}
      <button
        type="submit"
        disabled={isLoading}
        className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-sm shadow-lg shadow-teal-500/25 transition-all disabled:opacity-50"
      >
        <Play className="h-4 w-4 fill-slate-950" />
        <span>{isLoading ? 'Analyzing Safety Pipeline...' : 'Run Triage Analysis'}</span>
      </button>
    </form>
  )
}
