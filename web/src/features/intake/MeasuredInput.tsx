// Tri-state measured input component with polished clinical aesthetic

export type MeasurementStatus = 'measured' | 'estimated' | 'unknown'

export interface MeasuredValue<T> {
  value?: T | null
  status: MeasurementStatus
}

interface MeasuredInputProps<T extends string | number> {
  label: string
  unit?: string
  status: MeasurementStatus
  value?: T | null
  placeholder?: string
  type?: 'text' | 'number'
  step?: string
  onStatusChange: (status: MeasurementStatus) => void
  onValueChange: (value: T | null) => void
  helperText?: string
}

export function MeasuredInput<T extends string | number>({
  label,
  unit,
  status,
  value,
  placeholder,
  type = 'text',
  step,
  onStatusChange,
  onValueChange,
  helperText,
}: MeasuredInputProps<T>) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-slate-800">
          {label} {unit && <span className="text-teal-700 font-mono text-[11px]">({unit})</span>}
        </label>

        {/* Tri-state selector: Measured / Estimated / Unknown */}
        <div className="flex rounded-lg bg-slate-100 p-0.5 border border-slate-200 text-[10px] font-mono">
          <button
            type="button"
            onClick={() => onStatusChange('measured')}
            title="Objectively measured clinical value"
            className={`px-2 py-0.5 rounded-md transition-all ${
              status === 'measured'
                ? 'bg-white text-teal-800 font-bold shadow-soft-sm border border-teal-200'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Meas
          </button>
          <button
            type="button"
            onClick={() => onStatusChange('estimated')}
            title="Clinically estimated value"
            className={`px-2 py-0.5 rounded-md transition-all ${
              status === 'estimated'
                ? 'bg-amber-100 text-amber-900 font-bold shadow-soft-sm border border-amber-300'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Est
          </button>
          <button
            type="button"
            onClick={() => {
              onStatusChange('unknown')
              onValueChange(null)
            }}
            title="Unknown or unobtainable value (fails closed)"
            className={`px-2 py-0.5 rounded-md transition-all ${
              status === 'unknown'
                ? 'bg-violet-100 text-violet-900 font-bold shadow-soft-sm border border-violet-300'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            Unk
          </button>
        </div>
      </div>

      {status === 'unknown' ? (
        <div className="flex h-10 items-center rounded-xl border border-violet-200 bg-violet-50/70 px-3 text-xs italic text-violet-900 font-mono">
          Unknown / Unmeasured (Fail Closed)
        </div>
      ) : (
        <div className="relative flex items-center">
          <input
            type={type}
            step={step}
            value={value !== null && value !== undefined ? String(value) : ''}
            onChange={(e) => {
              const val = e.target.value
              if (val === '') {
                onValueChange(null)
              } else if (type === 'number') {
                const parsed = Number(val)
                onValueChange((isNaN(parsed) ? null : parsed) as T)
              } else {
                onValueChange(val as T)
              }
            }}
            placeholder={placeholder}
            className={`h-10 w-full rounded-xl border px-3 text-xs font-medium text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-500/20 ${
              status === 'estimated'
                ? 'border-amber-300 bg-amber-50/40 text-amber-950'
                : 'border-[#d9e8e6] bg-white'
            }`}
          />
          {unit && (
            <span className="pointer-events-none absolute right-3 text-[11px] font-mono font-medium text-slate-400">
              {unit}
            </span>
          )}
        </div>
      )}

      {helperText && <span className="text-[10px] text-slate-400 leading-tight">{helperText}</span>}
    </div>
  )
}

export default MeasuredInput
