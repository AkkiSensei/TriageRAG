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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-[#E1E7E1] bg-white p-6 shadow-2xl text-[#1A2421]">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[#E1E7E1] pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 border border-amber-300 text-amber-700 shadow-xs">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#1A2421]">Document Clinician Override</h3>
              <p className="text-xs text-[#5C6B64]">Audit-logged exception for HIGH severity clinical alert</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#5C6B64] hover:bg-[#EEF3EE] hover:text-[#1A2421] transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 shadow-xs">
            <div className="flex items-center gap-2 font-mono font-bold">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <span>Target Rule: {ruleId} &bull; Step #{stepNumber}</span>
            </div>
            <p className="mt-1 text-[11px] text-amber-800 leading-relaxed">
              Overrides are recorded permanently in the append-only SHA-256 audit log. This action does not weaken rules for other patients.
            </p>
          </div>

          <div>
            <label className="text-xs font-semibold text-[#1A2421]">Clinician ID / Attending Identifier</label>
            <input
              type="text"
              value={clinicianId}
              onChange={(e) => setClinicianId(e.target.value)}
              placeholder="e.g. DR-4092, ATTENDING-EM"
              className="mt-1 h-9 w-full rounded-lg border border-[#E1E7E1] bg-white px-3 text-xs text-[#1A2421] placeholder-[#8A9991] focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500/20 font-mono"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-[#1A2421]">
              Clinical Justification & Risk-Benefit Rationale <span className="text-[#5C6B64] font-mono">(min 15 chars)</span>
            </label>
            <textarea
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="State explicit clinical rationale (e.g., hemodynamics stable with continuous telemetry; benefits outweigh mild bradycardia risk...)"
              className="mt-1 w-full rounded-lg border border-[#E1E7E1] bg-white p-2.5 text-xs text-[#1A2421] placeholder-[#8A9991] focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500/20"
            />
            <div className="mt-1 flex justify-between text-[10px] text-[#5C6B64]">
              <span>Characters: {reason.trim().length} / 15 minimum</span>
              {reason.trim().length >= 15 && <span className="text-[#2D6A4F] font-mono font-bold">&check; Valid length</span>}
            </div>
          </div>

          {error && (
            <div className="rounded-xl bg-red-100 border border-red-200 p-2 text-xs text-red-900 font-medium">
              {error}
            </div>
          )}

          {/* Action buttons */}
          <div className="mt-2 flex items-center justify-end gap-3 pt-3 border-t border-[#E1E7E1]">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-[#E1E7E1] bg-white hover:bg-[#EEF3EE] px-4 py-2 text-xs font-semibold text-[#1A2421] transition-colors shadow-xs"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={reason.trim().length < 15}
              className="flex items-center gap-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 px-4 py-2 text-xs font-bold text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-xs"
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

