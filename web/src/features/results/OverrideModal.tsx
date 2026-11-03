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
  const [clinicianId, setClinicianId] = useState('Dr. Sharma (On-Duty)')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!clinicianId.trim()) {
      setError('Doctor Name / Registration ID is required')
      return
    }
    if (reason.trim().length < 15) {
      setError('Please provide a medical reason (at least 15 characters)')
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 dark:bg-black/80 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-lg rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 sm:p-7 shadow-xl text-slate-900 dark:text-white">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-100 dark:border-slate-700 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-100 dark:bg-amber-950/80 border border-amber-300 dark:border-amber-700 text-amber-800 dark:text-amber-300 shadow-sm">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">Doctor Review &amp; Approval</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">Confirmation for high-severity safety warning</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl p-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-4">
          <div className="rounded-2xl border border-amber-300 dark:border-amber-700 bg-amber-50/80 dark:bg-amber-950/40 p-3.5 text-xs text-amber-950 dark:text-amber-200 shadow-sm">
            <div className="flex items-center gap-2 font-bold">
              <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <span>Step #{stepNumber} Approval &bull; Rule: {ruleId}</span>
            </div>
            <p className="mt-1 text-xs text-amber-900/90 dark:text-amber-300/90 leading-relaxed">
              A doctor must confirm that the medical benefits of giving this medicine outweigh the risk for this specific patient.
            </p>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-800 dark:text-slate-200 block mb-1">
              Doctor Name / Medical Registration ID
            </label>
            <input
              type="text"
              value={clinicianId}
              onChange={(e) => setClinicianId(e.target.value)}
              placeholder="e.g. Dr. Rajesh Sharma, Reg-10492"
              className="h-10 w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3.5 text-xs sm:text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-800 dark:text-slate-200 block mb-1">
              Medical Reason &amp; Clinical Plan{' '}
              <span className="text-slate-400 dark:text-slate-500 text-xs font-normal">(minimum 15 characters)</span>
            </label>
            <textarea
              rows={4}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="State why this medicine is needed for this patient and what precautions are in place..."
              className="w-full rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 p-3 text-xs sm:text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 resize-none leading-relaxed"
            />
            <div className="mt-1 flex items-center justify-between text-xs text-slate-400 dark:text-slate-500">
              <span>{reason.length} characters</span>
              <span className={reason.length >= 15 ? 'text-teal-600 dark:text-teal-400 font-semibold' : 'text-amber-600 dark:text-amber-400'}>
                {reason.length >= 15 ? 'Length requirement met' : 'Min 15 characters needed'}
              </span>
            </div>
          </div>

          {error && (
            <div className="rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50 dark:bg-rose-950/60 p-2.5 text-xs text-rose-800 dark:text-rose-200 font-medium">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-700">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex items-center gap-1.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white px-5 py-2 text-xs font-bold shadow-sm transition-all cursor-pointer"
            >
              <Check className="h-4 w-4" />
              <span>Confirm &amp; Approve Step</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default OverrideModal