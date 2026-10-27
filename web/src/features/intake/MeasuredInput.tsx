// Tri-state measured input component

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
        <label className="text-xs font-medium text-slate-300">
          {label} {unit && <span className="text-slate-400 font-mono">({unit})</span>}
        </label>
        {/* Tri-state selector: Measured / Estimated / Unknown */}
        <div className="flex rounded bg-slate-950 p-0.5 border border-slate-800 text-[10px] font-mono">
          <button
            type="button"
            onClick={() => onStatusChange('measured')}
            className={`px-1.5 py-0.5 rounded transition-colors ${
              status === 'measured' ? 'bg-teal-500/20 text-teal-300 font-semibold' : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            Meas
          </button>
          <button
            type="button"
            onClick={() => onStatusChange('estimated')}
            className={`px-1.5 py-0.5 rounded transition-colors ${
              status === 'estimated' ? 'bg-amber-500/20 text-amber-300 font-semibold' : 'text-slate-400 hover:text-slate-300'
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
            className={`px-1.5 py-0.5 rounded transition-colors ${
              status === 'unknown' ? 'bg-purple-500/20 text-purple-300 font-semibold' : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            Unk
          </button>
        </div>
      </div>

      {status === 'unknown' ? (
        <div className="flex h-9 items-center rounded-md border border-purple-900/40 bg-purple-950/20 px-3 text-xs italic text-purple-300/80 font-mono">
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
            className={`h-9 w-full rounded-md border bg-slate-950 px-3 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-1 ${
              status === 'estimated'
                ? 'border-amber-700/60 focus:border-amber-500 focus:ring-amber-500/30'
                : 'border-slate-800 focus:border-teal-500 focus:ring-teal-500/30'
            }`}
          />
          {unit && (
            <span className="pointer-events-none absolute right-3 text-xs text-slate-400 font-mono">
              {unit}
            </span>
          )}
        </div>
      )}

      {helperText && <span className="text-[10px] text-slate-400">{helperText}</span>}
    </div>
  )
}
