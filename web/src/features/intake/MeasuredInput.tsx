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
        <label className="text-xs font-semibold text-[#1A2421]">
          {label} {unit && <span className="text-[#5C6B64] font-mono">({unit})</span>}
        </label>
        {/* Tri-state selector: Measured / Estimated / Unknown */}
        <div className="flex rounded-md bg-[#F4F6F4] p-0.5 border border-[#E1E7E1] text-[10px] font-mono">
          <button
            type="button"
            onClick={() => onStatusChange('measured')}
            className={`px-1.5 py-0.5 rounded transition-colors ${
              status === 'measured'
                ? 'bg-white text-[#2D6A4F] font-bold shadow-xs border border-[#C4CEBD]'
                : 'text-[#5C6B64] hover:text-[#1A2421]'
            }`}
          >
            Meas
          </button>
          <button
            type="button"
            onClick={() => onStatusChange('estimated')}
            className={`px-1.5 py-0.5 rounded transition-colors ${
              status === 'estimated'
                ? 'bg-amber-100 text-amber-900 font-bold shadow-xs border border-amber-300'
                : 'text-[#5C6B64] hover:text-[#1A2421]'
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
              status === 'unknown'
                ? 'bg-purple-100 text-purple-900 font-bold shadow-xs border border-purple-300'
                : 'text-[#5C6B64] hover:text-[#1A2421]'
            }`}
          >
            Unk
          </button>
        </div>
      </div>

      {status === 'unknown' ? (
        <div className="flex h-9 items-center rounded-lg border border-purple-200 bg-purple-50/70 px-3 text-xs italic text-purple-900 font-mono">
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
            className={`h-9 w-full rounded-lg border bg-white px-3 text-xs text-[#1A2421] placeholder-[#8A9991] focus:outline-none focus:ring-2 ${
              status === 'estimated'
                ? 'border-amber-300 focus:border-amber-500 focus:ring-amber-500/20'
                : 'border-[#E1E7E1] focus:border-[#2D6A4F] focus:ring-[#2D6A4F]/20'
            }`}
          />
          {unit && (
            <span className="pointer-events-none absolute right-3 text-xs text-[#5C6B64] font-mono">
              {unit}
            </span>
          )}
        </div>
      )}

      {helperText && <span className="text-[10px] text-[#5C6B64]">{helperText}</span>}
    </div>
  )
}

