// Tri-state measured input component with polished clinical aesthetic in light and dark mode

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
    <div className="flex flex-col gap-2 rounded-2xl border border-slate-200/90 dark:border-slate-700/80 bg-slate-50/60 dark:bg-slate-800/40 p-3 transition-all hover:border-slate-300 dark:hover:border-slate-600">
      {/* Row 1: Label and Unit cleanly separated */}
      <div className="flex items-baseline justify-between gap-1">
        <label className="text-xs font-bold text-slate-800 dark:text-slate-200 truncate" title={label}>
          {label}
        </label>
        {unit && (
          <span className="text-[11px] font-mono font-semibold text-teal-700 dark:text-teal-400 shrink-0">
            {unit}
          </span>
        )}
      </div>

      {/* Row 2: Status Pill Segments spanning full width of card */}
      <div className="grid grid-cols-3 rounded-lg bg-slate-200/70 dark:bg-slate-700/70 p-0.5 border border-slate-200 dark:border-slate-600 text-[10px]">
        <button
          type="button"
          onClick={() => onStatusChange('measured')}
          title="Objectively measured clinical value"
          className={`py-1 rounded-md font-semibold transition-all text-center truncate ${
            status === 'measured'
              ? 'bg-white dark:bg-slate-600 text-teal-800 dark:text-teal-300 font-bold shadow-soft-sm border border-teal-200 dark:border-teal-700'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          Measured
        </button>
        <button
          type="button"
          onClick={() => onStatusChange('estimated')}
          title="Clinically estimated value"
          className={`py-1 rounded-md font-semibold transition-all text-center truncate ${
            status === 'estimated'
              ? 'bg-amber-100 dark:bg-amber-950/70 text-amber-900 dark:text-amber-300 font-bold shadow-soft-sm border border-amber-300 dark:border-amber-700'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          Estimated
        </button>
        <button
          type="button"
          onClick={() => {
            onStatusChange('unknown')
            onValueChange(null)
          }}
          title="Unknown or not recorded"
          className={`py-1 rounded-md font-semibold transition-all text-center truncate ${
            status === 'unknown'
              ? 'bg-violet-100 dark:bg-violet-950/70 text-violet-900 dark:text-violet-300 font-bold shadow-soft-sm border border-violet-300 dark:border-violet-700'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
          }`}
        >
          Unknown
        </button>
      </div>

      {/* Row 3: Numeric Input OR Unknown Placeholder */}
      {status === 'unknown' ? (
        <div className="flex h-10 items-center justify-center rounded-xl border border-dashed border-violet-300/80 dark:border-violet-800/80 bg-violet-50/70 dark:bg-violet-950/40 px-3 text-xs italic text-violet-900 dark:text-violet-300 select-none">
          Not recorded / Unknown
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
            className={`h-10 w-full rounded-xl border px-3 text-xs font-medium text-slate-900 dark:text-white outline-none transition-all placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:border-teal-600 focus:ring-2 focus:ring-teal-500/20 dark:focus:border-teal-400 ${
              status === 'estimated'
                ? 'border-amber-300 dark:border-amber-700/80 bg-amber-50/40 dark:bg-amber-950/30 text-amber-950 dark:text-amber-200'
                : 'border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800'
            }`}
          />
          {unit && (
            <span className="pointer-events-none absolute right-3 text-[11px] font-mono font-medium text-slate-400 dark:text-slate-500">
              {unit}
            </span>
          )}
        </div>
      )}

      {helperText && (
        <span className="text-[10px] text-slate-400 dark:text-slate-500 leading-tight">
          {helperText}
        </span>
      )}
    </div>
  )
}

export default MeasuredInput
