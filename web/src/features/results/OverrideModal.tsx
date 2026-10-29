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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-6 sm:p-7 shadow-soft-xl text-slate-900">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-100 border border-amber-300 text-amber-800 shadow-soft-sm">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Document Clinician Override</h3>
              <p className="text-xs text-slate-500">Audit-logged exception for HIGH severity clinical alert</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-800 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          <div className="rounded-2xl border border-amber-300 bg-amber-50/80 p-3.5 text-xs text-amber-950 shadow-soft-sm">
            <div className="flex items-center gap-2 font-mono font-bold">
              <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
              <span>Target Rule: {ruleId} &bull; Step #{stepNumber}</span>
            </div>
            <p className="mt-1 text-[11px] text-amber-900/90 leading-relaxed">
              Overrides are recorded permanently into the append-only SHA-256 Merkle audit chain with your clinician credentials.
            </p>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-800">
              Clinician ID / Attending Identifier
            </label>
            <input
              type="text"
              value={clinicianId}
              onChange={(e) => setClinicianId(e.target.value)}
              placeholder="e.g. DR-4092, ATTENDING-EM"
              className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 bg-white px-3.5 text-xs text-slate-900 placeholder-slate-400 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 font-mono"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-800">
              Clinical Justification &amp; Risk-Benefit Rationale{' '}
              <span className="text-slate-400 font-mono text-[11px]">(minimum 15 characters)</span>
            </label>
            <textarea
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="State patient-specific rationale, alternative therapies tried, and risk mitigation plan..."
              className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-900 placeholder-slate-400 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 resize-none leading-relaxed"
            />
            <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400 font-mono">
              <span>{reason.length} characters</span>
              <span className={reason.length >= 15 ? 'text-teal-700 font-semibold' : 'text-amber-600'}>
                {reason.length >= 15 ? 'Validation met' : 'Min 15 required'}
              </span>
            </div>
          </div>

          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-800">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex items-center gap-2 rounded-xl bg-amber-600 hover:bg-amber-700 px-5 py-2 text-xs font-bold text-white shadow-soft transition-all"
            >
              <Check className="h-4 w-4" />
              <span>Record &amp; Sign Override</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default OverrideModal
