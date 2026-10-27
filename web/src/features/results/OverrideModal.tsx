import React, { useState } from 'react'
import { AlertTriangle, X, ShieldAlert, Check } from 'lucide-react'
import type { OverrideRecord } from '@/lib/api'

interface OverrideModalProps {
  isOpen: boolean
  ruleId: string
  stepNumber: number
  onClose: () => void
  onSubmit: (override: OverrideRecord) => void
}

export const OverrideModal: React.FC<OverrideModalProps> = ({
  isOpen,
  ruleId,
  stepNumber,
  onClose,
  onSubmit,
}) => {
  const [clinicianId, setClinicianId] = useState('DR-ONCALL-104')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!clinicianId.trim()) {
      setError('Clinician ID / License Number is required')
      return
    }
    if (reason.trim().length < 15) {
      setError('Clinical justification must be at least 15 characters long')
      return
    }

    setError(null)
    onSubmit({
      rule_id: ruleId,
      step_number: stepNumber,
      reason: reason.trim(),
      clinician_id: clinicianId.trim(),
    })
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-amber-800/80 bg-slate-950 p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100">Document Clinician Override</h3>
              <p className="text-xs text-slate-400">Audit-logged exception for HIGH severity clinical alert</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-900 hover:text-slate-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 p-3 text-xs text-amber-200">
            <div className="flex items-center gap-2 font-mono font-semibold">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              <span>Target Rule: {ruleId} &bull; Step #{stepNumber}</span>
            </div>
            <p className="mt-1 text-[11px] text-amber-300/80">
              Overrides are recorded permanently in the append-only SHA-256 audit log. This action does not weaken rules for other patients.
            </p>
          </div>

          <div>
            <label className="text-xs font-medium text-slate-300">Clinician ID / Attending Identifier</label>
            <input
              type="text"
              value={clinicianId}
              onChange={(e) => setClinicianId(e.target.value)}
              placeholder="e.g. DR-4092, ATTENDING-EM"
              className="mt-1 h-9 w-full rounded-md border border-slate-800 bg-slate-900 px-3 text-xs text-slate-100 focus:border-amber-500 focus:outline-none font-mono"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-slate-300">
              Clinical Justification & Risk-Benefit Rationale <span className="text-slate-400 font-mono">(min 15 chars)</span>
            </label>
            <textarea
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="State explicit clinical rationale (e.g., hemodynamics stable with continuous telemetry; benefits outweigh mild bradycardia risk...)"
              className="mt-1 w-full rounded-md border border-slate-800 bg-slate-900 p-2.5 text-xs text-slate-100 placeholder-slate-600 focus:border-amber-500 focus:outline-none"
            />
            <div className="mt-1 flex justify-between text-[10px] text-slate-400">
              <span>Characters: {reason.trim().length} / 15 minimum</span>
              {reason.trim().length >= 15 && <span className="text-teal-400 font-mono">&check; Valid length</span>}
            </div>
          </div>

          {error && (
            <div className="rounded bg-red-950/60 border border-red-900 p-2 text-xs text-red-300">
              {error}
            </div>
          )}

          {/* Action buttons */}
          <div className="mt-2 flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={reason.trim().length < 15}
              className="flex items-center gap-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 px-4 py-2 text-xs font-bold text-slate-950 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Check className="h-4 w-4" />
              Sign & Record Override
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
