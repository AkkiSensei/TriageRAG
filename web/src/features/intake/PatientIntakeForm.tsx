import React, { useState } from 'react'
import { MeasuredInput, type MeasurementStatus } from './MeasuredInput'
import { ScenarioSelector } from './ScenarioSelector'
import type { TriageApiRequest, ScenarioDetail } from '@/lib/api'
import type { components } from '@/types/api'
import { Plus, Trash2, Play, RotateCcw, AlertTriangle, ShieldCheck, Heart, Stethoscope, Pill, ShieldAlert } from 'lucide-react'

type AgeUnit = components['schemas']['AgeUnit']
type Sex = 'male' | 'female' | 'other' | 'unknown'
type Pregnancy = 'yes' | 'no' | 'not_applicable' | 'unknown'
type Consciousness = components['schemas']['Consciousness']
type HistoryStatus = 'confirmed_none' | 'confirmed_nkda' | 'confirmed_list' | 'incomplete' | 'unknown_unobtainable'
type ReactionType = 'anaphylaxis_ige' | 'severe_cutaneous_scar' | 'mild_rash' | 'gi_upset' | 'unknown'
type Impairment = 'yes' | 'no' | 'unknown'
type LLMProfile = 'COMPLIANT' | 'INVENT_DRUG' | 'PROSE_LEAK' | 'INVALID_CITATION' | 'IGNORE_BLOCK' | 'OBEY_COMPLAINT' | 'NAIVE_FREE_TEXT'

interface PatientIntakeFormProps {
  onSubmit: (request: TriageApiRequest) => void
  isLoading?: boolean
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

const INITIAL_FORM_STATE: FormState = {
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

export const PatientIntakeForm: React.FC<PatientIntakeFormProps> = ({ onSubmit, isLoading }) => {
  const [form, setForm] = useState<FormState>(INITIAL_FORM_STATE)
  const [activeTab, setActiveTab] = useState<'demographics' | 'vitals' | 'meds' | 'allergies' | 'context'>('demographics')

  const handleScenarioLoad = (scenario: ScenarioDetail) => {
    const p = scenario.patient
    const rawConsciousness = (p.vitals.consciousness?.value as string) || 'A'
    const validConsciousness: Consciousness =
      rawConsciousness === 'A' || rawConsciousness === 'C' || rawConsciousness === 'V' || rawConsciousness === 'P' || rawConsciousness === 'U'
        ? (rawConsciousness as Consciousness)
        : 'A'

    setForm({
      ageValue: String(p.age.value),
      ageUnit: (p.age.unit as AgeUnit) || 'years',
      sex: p.sex as Sex,
      pregnancy: p.pregnancy as Pregnancy,
      weightStatus: (p.weight_kg.source as MeasurementStatus) || 'measured',
      weightValue: p.weight_kg.value !== null && p.weight_kg.value !== undefined ? String(p.weight_kg.value) : '',

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
      tempValue: p.vitals.temperature_c?.value !== null && p.vitals.temperature_c?.value !== undefined ? String(p.vitals.temperature_c.value) : '',
      glucoseStatus: (p.vitals.blood_glucose_mg_dl?.source as MeasurementStatus) || 'unknown',
      glucoseValue: p.vitals.blood_glucose_mg_dl?.value !== null && p.vitals.blood_glucose_mg_dl?.value !== undefined ? String(p.vitals.blood_glucose_mg_dl.value) : '',
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
        pregnancy: form.pregnancy,
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(buildApiPayload())
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      {/* Quick Scenario Loader Bar */}
      <ScenarioSelector onSelectScenario={handleScenarioLoad} />

      {/* Tabs / Step Navigation */}
      <div className="flex rounded-lg bg-slate-900 border border-slate-800 p-1 text-xs">
        <button
          type="button"
          onClick={() => setActiveTab('demographics')}
          className={`flex-1 py-1.5 px-2 rounded-md font-medium transition-all ${
            activeTab === 'demographics' ? 'bg-teal-500/20 text-teal-300 font-semibold shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Demographics
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('vitals')}
          className={`flex-1 py-1.5 px-2 rounded-md font-medium transition-all ${
            activeTab === 'vitals' ? 'bg-teal-500/20 text-teal-300 font-semibold shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Vitals
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('meds')}
          className={`flex-1 py-1.5 px-2 rounded-md font-medium transition-all ${
            activeTab === 'meds' ? 'bg-teal-500/20 text-teal-300 font-semibold shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Meds ({form.medications.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('allergies')}
          className={`flex-1 py-1.5 px-2 rounded-md font-medium transition-all ${
            activeTab === 'allergies' ? 'bg-teal-500/20 text-teal-300 font-semibold shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Allergies ({form.allergies.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('context')}
          className={`flex-1 py-1.5 px-2 rounded-md font-medium transition-all ${
            activeTab === 'context' ? 'bg-teal-500/20 text-teal-300 font-semibold shadow' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Context
        </button>
      </div>

      {/* Tab Panels */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        {/* DEMOGRAPHICS */}
        {activeTab === 'demographics' && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-teal-400 border-b border-slate-800 pb-2">
              <Stethoscope className="h-4 w-4" />
              <span>Patient Identification & Physical Metrics</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-slate-300">Chronological Age</label>
                <div className="mt-1 flex gap-2">
                  <input
                    type="text"
                    value={form.ageValue}
                    onChange={(e) => setForm({ ...form, ageValue: e.target.value })}
                    placeholder="e.g. 62"
                    className="h-9 w-2/3 rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-100 focus:border-teal-500 focus:outline-none"
                  />
                  <select
                    value={form.ageUnit}
                    onChange={(e) => setForm({ ...form, ageUnit: e.target.value as AgeUnit })}
                    className="h-9 w-1/3 rounded-md border border-slate-800 bg-slate-950 px-2 text-xs text-slate-300 focus:border-teal-500 focus:outline-none"
                  >
                    <option value="years">Years</option>
                    <option value="months">Months</option>
                    <option value="days">Days</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300">Biological Sex</label>
                <select
                  value={form.sex}
                  onChange={(e) => setForm({ ...form, sex: e.target.value as Sex })}
                  className="mt-1 h-9 w-full rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-300 focus:border-teal-500 focus:outline-none"
                >
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                  <option value="unknown">Unknown</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300">Pregnancy Status</label>
                <select
                  value={form.pregnancy}
                  onChange={(e) => setForm({ ...form, pregnancy: e.target.value as Pregnancy })}
                  className="mt-1 h-9 w-full rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-300 focus:border-teal-500 focus:outline-none"
                >
                  <option value="no">Not Pregnant (No)</option>
                  <option value="yes">Confirmed Pregnant (Yes)</option>
                  <option value="not_applicable">Not Applicable</option>
                  <option value="unknown">Unknown</option>
                </select>
              </div>

              <MeasuredInput
                label="Weight"
                unit="kg"
                status={form.weightStatus}
                value={form.weightValue}
                placeholder="e.g. 82.0"
                onStatusChange={(status) => setForm({ ...form, weightStatus: status })}
                onValueChange={(val) => setForm({ ...form, weightValue: val || '' })}
                helperText="Required for weight-scaled paediatric dosing math."
              />
            </div>
          </div>
        )}

        {/* VITALS */}
        {activeTab === 'vitals' && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-teal-400 border-b border-slate-800 pb-2">
              <Heart className="h-4 w-4" />
              <span>Physiological Vital Signs (Measured / Estimated / Unknown)</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <MeasuredInput
                label="Heart Rate"
                unit="bpm"
                type="number"
                status={form.hrStatus}
                value={form.hrValue}
                placeholder="e.g. 92"
                onStatusChange={(status) => setForm({ ...form, hrStatus: status })}
                onValueChange={(val) => setForm({ ...form, hrValue: val })}
              />

              <MeasuredInput
                label="Systolic BP"
                unit="mmHg"
                type="number"
                status={form.sbpStatus}
                value={form.sbpValue}
                placeholder="e.g. 135"
                onStatusChange={(status) => setForm({ ...form, sbpStatus: status })}
                onValueChange={(val) => setForm({ ...form, sbpValue: val })}
              />

              <MeasuredInput
                label="Diastolic BP"
                unit="mmHg"
                type="number"
                status={form.dbpStatus}
                value={form.dbpValue}
                placeholder="e.g. 85"
                onStatusChange={(status) => setForm({ ...form, dbpStatus: status })}
                onValueChange={(val) => setForm({ ...form, dbpValue: val })}
              />

              <MeasuredInput
                label="Respiratory Rate"
                unit="bpm"
                type="number"
                status={form.rrStatus}
                value={form.rrValue}
                placeholder="e.g. 18"
                onStatusChange={(status) => setForm({ ...form, rrStatus: status })}
                onValueChange={(val) => setForm({ ...form, rrValue: val })}
              />

              <MeasuredInput
                label="Oxygen Saturation (SpO2)"
                unit="%"
                type="number"
                status={form.spo2Status}
                value={form.spo2Value}
                placeholder="e.g. 98"
                onStatusChange={(status) => setForm({ ...form, spo2Status: status })}
                onValueChange={(val) => setForm({ ...form, spo2Value: val })}
              />

              <MeasuredInput
                label="Body Temperature"
                unit="°C"
                status={form.tempStatus}
                value={form.tempValue}
                placeholder="e.g. 37.1"
                onStatusChange={(status) => setForm({ ...form, tempStatus: status })}
                onValueChange={(val) => setForm({ ...form, tempValue: val || '' })}
              />

              <MeasuredInput
                label="Blood Glucose"
                unit="mg/dL"
                status={form.glucoseStatus}
                value={form.glucoseValue}
                placeholder="e.g. 110.0"
                onStatusChange={(status) => setForm({ ...form, glucoseStatus: status })}
                onValueChange={(val) => setForm({ ...form, glucoseValue: val || '' })}
              />

              <div>
                <label className="text-xs font-medium text-slate-300">Consciousness Level (AVPU+C)</label>
                <select
                  value={form.consciousnessValue}
                  onChange={(e) => setForm({ ...form, consciousnessValue: e.target.value as Consciousness })}
                  className="mt-1 h-9 w-full rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-300 focus:border-teal-500 focus:outline-none font-mono"
                >
                  <option value="A">Alert (A)</option>
                  <option value="C">New Confusion (C)</option>
                  <option value="V">Responds to Voice (V)</option>
                  <option value="P">Responds to Pain (P)</option>
                  <option value="U">Unresponsive (U)</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* MEDICATIONS */}
        {activeTab === 'meds' && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-teal-400">
                <Pill className="h-4 w-4" />
                <span>Medication History (R2: Incomplete fails closed)</span>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-slate-300">Medication History Status</label>
              <select
                value={form.medicationStatus}
                onChange={(e) => setForm({ ...form, medicationStatus: e.target.value as HistoryStatus })}
                className="mt-1 h-9 w-full rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-300 focus:border-teal-500 focus:outline-none font-mono"
              >
                <option value="confirmed_list">Confirmed List (Explicit Medication Entries)</option>
                <option value="confirmed_none">Confirmed None (No current medications)</option>
                <option value="confirmed_nkda">Confirmed NKDA</option>
                <option value="incomplete">Incomplete History (Triggers UNVERIFIED)</option>
                <option value="unknown_unobtainable">Unknown / Unobtainable (Triggers UNVERIFIED)</option>
              </select>
            </div>

            <div className="flex flex-col gap-2 mt-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Current Regular / Acute Medications:</span>
                <button
                  type="button"
                  onClick={() => setForm({ ...form, medications: [...form.medications, { raw_string: '' }] })}
                  className="flex items-center gap-1 text-[11px] font-mono text-teal-400 hover:text-teal-300"
                >
                  <Plus className="h-3 w-3" /> Add Medication
                </button>
              </div>

              {form.medications.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-800 p-4 text-center text-xs text-slate-400">
                  No medications entered. If patient takes no medications, ensure history status is &ldquo;Confirmed None&rdquo;.
                </div>
              ) : (
                form.medications.map((med, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={med.raw_string}
                      onChange={(e) => {
                        const copy = [...form.medications]
                        copy[idx].raw_string = e.target.value
                        setForm({ ...form, medications: copy })
                      }}
                      placeholder="e.g. Sildenafil 50mg daily, Metoprolol 25mg"
                      className="h-9 flex-1 rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-100 focus:border-teal-500 focus:outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setForm({
                          ...form,
                          medications: form.medications.filter((_, i) => i !== idx),
                        })
                      }}
                      className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-800 text-slate-400 hover:border-red-900/60 hover:text-red-400"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* ALLERGIES */}
        {activeTab === 'allergies' && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-teal-400">
                <ShieldAlert className="h-4 w-4" />
                <span>Substance Allergies & Hypersensitivities</span>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-slate-300">Allergy History Status</label>
              <select
                value={form.allergyStatus}
                onChange={(e) => setForm({ ...form, allergyStatus: e.target.value as HistoryStatus })}
                className="mt-1 h-9 w-full rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-300 focus:border-teal-500 focus:outline-none font-mono"
              >
                <option value="confirmed_list">Confirmed List (Explicit Allergy Entries)</option>
                <option value="confirmed_nkda">Confirmed NKDA (No Known Drug Allergies)</option>
                <option value="confirmed_none">Confirmed None</option>
                <option value="incomplete">Incomplete History (Triggers UNVERIFIED)</option>
                <option value="unknown_unobtainable">Unknown / Unobtainable (Triggers UNVERIFIED)</option>
              </select>
            </div>

            <div className="flex flex-col gap-2 mt-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Known Drug Allergies & Reaction Phenotypes:</span>
                <button
                  type="button"
                  onClick={() =>
                    setForm({
                      ...form,
                      allergies: [...form.allergies, { raw_substance: '', reaction_type: 'anaphylaxis_ige' }],
                    })
                  }
                  className="flex items-center gap-1 text-[11px] font-mono text-teal-400 hover:text-teal-300"
                >
                  <Plus className="h-3 w-3" /> Add Allergy
                </button>
              </div>

              {form.allergies.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-800 p-4 text-center text-xs text-slate-400">
                  No allergies entered. If patient has no allergies, set status to &ldquo;Confirmed NKDA&rdquo;.
                </div>
              ) : (
                form.allergies.map((all, idx) => (
                  <div key={idx} className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
                    <input
                      type="text"
                      value={all.raw_substance}
                      onChange={(e) => {
                        const copy = [...form.allergies]
                        copy[idx].raw_substance = e.target.value
                        setForm({ ...form, allergies: copy })
                      }}
                      placeholder="e.g. Penicillin, Amoxicillin, Ceftriaxone"
                      className="h-9 flex-1 rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-100 focus:border-teal-500 focus:outline-none"
                    />
                    <select
                      value={all.reaction_type}
                      onChange={(e) => {
                        const copy = [...form.allergies]
                        copy[idx].reaction_type = e.target.value as ReactionType
                        setForm({ ...form, allergies: copy })
                      }}
                      className="h-9 rounded-md border border-slate-800 bg-slate-950 px-2 text-xs text-slate-300 focus:border-teal-500 focus:outline-none font-mono"
                    >
                      <option value="anaphylaxis_ige">IgE Anaphylaxis (BLOCK)</option>
                      <option value="severe_cutaneous_scar">SCAR / SJS / TEN (BLOCK)</option>
                      <option value="mild_rash">Mild Rash (HIGH alert)</option>
                      <option value="gi_upset">GI Upset (INFO)</option>
                      <option value="unknown">Unknown Reaction (UNVERIFIED)</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => {
                        setForm({
                          ...form,
                          allergies: form.allergies.filter((_, i) => i !== idx),
                        })
                      }}
                      className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-800 text-slate-400 hover:border-red-900/60 hover:text-red-400"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* CONTEXT & UNTRUSTED COMPLAINT */}
        {activeTab === 'context' && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-teal-400 border-b border-slate-800 pb-2">
              <ShieldCheck className="h-4 w-4" />
              <span>Suspected Clinical Syndrome & Organ Function</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="text-xs font-medium text-slate-300">Suspected Syndrome</label>
                <select
                  value={form.suspectedSyndrome}
                  onChange={(e) => setForm({ ...form, suspectedSyndrome: e.target.value })}
                  className="mt-1 h-9 w-full rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-300 focus:border-teal-500 focus:outline-none"
                >
                  <option value="chest_pain">Chest Pain / ACS STEMI</option>
                  <option value="anaphylaxis">Severe Anaphylaxis</option>
                  <option value="asthma_severe">Acute Severe Asthma</option>
                  <option value="hypoglycemia">Severe Hypoglycemia</option>
                  <option value="sepsis">Sepsis / Septic Shock</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300">Renal Impairment</label>
                <select
                  value={form.renalImpairment}
                  onChange={(e) => setForm({ ...form, renalImpairment: e.target.value as Impairment })}
                  className="mt-1 h-9 w-full rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-300 focus:border-teal-500 focus:outline-none font-mono"
                >
                  <option value="no">Normal (No)</option>
                  <option value="yes">Impaired (Yes)</option>
                  <option value="unknown">Unknown</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300">Hepatic Impairment</label>
                <select
                  value={form.hepaticImpairment}
                  onChange={(e) => setForm({ ...form, hepaticImpairment: e.target.value as Impairment })}
                  className="mt-1 h-9 w-full rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-300 focus:border-teal-500 focus:outline-none font-mono"
                >
                  <option value="no">Normal (No)</option>
                  <option value="yes">Impaired (Yes)</option>
                  <option value="unknown">Unknown</option>
                </select>
              </div>
            </div>

            {/* R7 Untrusted Chief Complaint Isolation Box */}
            <div className="mt-2 rounded-lg border border-amber-800/60 bg-amber-950/20 p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-amber-400">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <span>Untrusted Chief Complaint (R7 Isolation)</span>
                </div>
                <span className="text-[10px] font-mono text-amber-400/80">Never parsed by Engine</span>
              </div>
              <textarea
                value={form.chiefComplaint}
                onChange={(e) => setForm({ ...form, chiefComplaint: e.target.value })}
                rows={3}
                placeholder="Free text narrative entered by triage nurse or patient..."
                className="w-full rounded-md border border-amber-900/60 bg-slate-950 p-2.5 text-xs text-slate-100 placeholder-slate-600 focus:border-amber-500 focus:outline-none"
              />
              <div className="mt-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  id="includeComplaint"
                  checked={form.includeComplaintInLlm}
                  onChange={(e) => setForm({ ...form, includeComplaintInLlm: e.target.checked })}
                  className="rounded border-slate-700 bg-slate-950 text-teal-500 focus:ring-0"
                />
                <label htmlFor="includeComplaint" className="text-[11px] text-slate-400 cursor-pointer">
                  Pass delimited complaint to LLM draft prompt (Default OFF; engine remains 100% isolated)
                </label>
              </div>
            </div>

            {/* LLM Profile Selection (Red-team simulator) */}
            <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950 p-3">
              <div>
                <span className="text-xs font-semibold text-slate-300">LLM Drafter Behavior Profile:</span>
                <p className="text-[10px] text-slate-400">Simulate compliant drafting or adversarial LLM failures.</p>
              </div>
              <select
                value={form.llmProfile}
                onChange={(e) => setForm({ ...form, llmProfile: e.target.value as LLMProfile })}
                className="h-8 rounded-md border border-slate-800 bg-slate-900 px-2 text-xs font-mono text-teal-400 focus:outline-none"
              >
                <option value="COMPLIANT">COMPLIANT (Safe Standard)</option>
                <option value="INVENT_DRUG">INVENT_DRUG (Hallucinated Medication)</option>
                <option value="PROSE_LEAK">PROSE_LEAK (Markdown formatting)</option>
                <option value="INVALID_CITATION">INVALID_CITATION (Forged chunk ID)</option>
                <option value="IGNORE_BLOCK">IGNORE_BLOCK (Attempt blocked drug)</option>
                <option value="OBEY_COMPLAINT">OBEY_COMPLAINT (Complies with injection)</option>
                <option value="NAIVE_FREE_TEXT">NAIVE_FREE_TEXT (Unstructured prose)</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Form Submission Bar */}
      <div className="flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => setForm(INITIAL_FORM_STATE)}
          className="flex items-center gap-1.5 rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
        >
          <RotateCcw className="h-3.5 w-3.5" /> Reset Form
        </button>

        <button
          type="submit"
          disabled={isLoading}
          className="flex items-center gap-2 rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 px-5 py-2.5 text-xs font-bold shadow-lg shadow-teal-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play className="h-4 w-4 fill-slate-950" />
          {isLoading ? 'Running Deterministic Engine...' : 'Run Triage Decision Support'}
        </button>
      </div>
    </form>
  )
}
