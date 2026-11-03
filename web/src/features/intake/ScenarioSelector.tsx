import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type ScenarioDetail } from '@/lib/api'
import { AlertOctagon, HelpCircle, AlertTriangle, CheckCircle, Loader2, Sparkles } from 'lucide-react'

interface ScenarioSelectorProps {
  onSelectScenario: (scenario: ScenarioDetail, autoRun?: boolean) => void
  activeScenarioId?: string | null
  loadingScenarioId?: string | null
}

export const ScenarioSelector: React.FC<ScenarioSelectorProps> = ({
  onSelectScenario,
  activeScenarioId,
  loadingScenarioId,
}) => {
  const { data: scenarios, isLoading } = useQuery({
    queryKey: ['scenarios'],
    queryFn: api.getScenarios,
  })

  const handleSelect = async (id: string, autoRun: boolean = true) => {
    try {
      const detail = await api.getScenario(id)
      onSelectScenario(detail, autoRun)
    } catch (err) {
      console.error('Failed to load scenario:', err)
    }
  }

  const getVerdictStyle = (band: string) => {
    switch (band.toUpperCase()) {
      case 'BLOCK':
      case 'BLOCKED':
        return {
          icon: <AlertOctagon className="h-4 w-4 text-rose-600 dark:text-rose-400 shrink-0" />,
          label: 'DANGER / STOP',
          subtitle: 'Harmful Medicine Combination',
          container:
            'border-rose-200 dark:border-rose-900/60 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 hover:border-rose-400 dark:hover:border-rose-600 hover:shadow-soft',
          activeContainer:
            'border-rose-500 dark:border-rose-500 bg-rose-50/80 dark:bg-rose-950/40 text-rose-950 dark:text-rose-100 font-semibold ring-2 ring-rose-500/25 shadow-soft',
          badge: 'bg-rose-100 dark:bg-rose-900/70 text-rose-800 dark:text-rose-200 border-rose-200 dark:border-rose-800 font-bold',
        }
      case 'HIGH':
      case 'CHECKED_ALERTS':
        return {
          icon: <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />,
          label: 'DOCTOR REVIEW',
          subtitle: 'Allergy Warning Needs Approval',
          container:
            'border-amber-200 dark:border-amber-900/60 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 hover:border-amber-400 dark:hover:border-amber-600 hover:shadow-soft',
          activeContainer:
            'border-amber-500 dark:border-amber-500 bg-amber-50/80 dark:bg-amber-950/40 text-amber-950 dark:text-amber-100 font-semibold ring-2 ring-amber-500/25 shadow-soft',
          badge: 'bg-amber-100 dark:bg-amber-900/70 text-amber-800 dark:text-amber-200 border-amber-200 dark:border-amber-800 font-bold',
        }
      case 'UNVERIFIED':
        return {
          icon: <HelpCircle className="h-4 w-4 text-violet-600 dark:text-violet-400 shrink-0" />,
          label: 'INCOMPLETE',
          subtitle: 'Missing Vitals / Cannot Clear',
          container:
            'border-violet-200 dark:border-violet-900/60 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 hover:border-violet-400 dark:hover:border-violet-600 hover:shadow-soft',
          activeContainer:
            'border-violet-500 dark:border-violet-500 bg-violet-50/80 dark:bg-violet-950/40 text-violet-950 dark:text-violet-100 font-semibold ring-2 ring-violet-500/25 shadow-soft',
          badge: 'bg-violet-100 dark:bg-violet-900/70 text-violet-800 dark:text-violet-200 border-violet-200 dark:border-violet-800 font-bold',
        }
      case 'CHECKED_CLEAR':
      case 'CLEAR':
      default:
        return {
          icon: <CheckCircle className="h-4 w-4 text-teal-600 dark:text-teal-400 shrink-0" />,
          label: 'ALL CLEAR',
          subtitle: 'Safe Emergency Process',
          container:
            'border-teal-200 dark:border-teal-900/60 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 hover:border-teal-400 dark:hover:border-teal-600 hover:shadow-soft',
          activeContainer:
            'border-teal-600 dark:border-teal-400 bg-teal-50 dark:bg-teal-950/50 text-teal-950 dark:text-teal-100 font-semibold ring-2 ring-teal-600/25 shadow-soft',
          badge: 'bg-teal-100 dark:bg-teal-900/70 text-teal-900 dark:text-teal-200 border-teal-200 dark:border-teal-800 font-bold',
        }
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2.5 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 text-xs text-slate-500 dark:text-slate-400 shadow-soft-sm">
        <Loader2 className="h-4 w-4 animate-spin text-teal-600 dark:text-teal-400" />
        <span>Loading sample patients...</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 sm:p-5 shadow-soft transition-all">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-teal-50 dark:bg-teal-950/80 text-teal-700 dark:text-teal-300">
            <Sparkles className="h-3.5 w-3.5" />
          </div>
          <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
            Try A Sample Patient (1-Click)
          </span>
        </div>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          Click to load &amp; see steps
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {scenarios?.map((s) => {
          const isLoadingThis = loadingScenarioId === s.id
          const isActive = activeScenarioId === s.id
          const style = getVerdictStyle(s.expected_verdict)

          return (
            <button
              key={s.id}
              type="button"
              onClick={() => handleSelect(s.id, true)}
              disabled={isLoadingThis}
              className={`relative flex flex-col justify-between rounded-2xl border p-4 text-left transition-all duration-200 ${
                isActive ? style.activeContainer : style.container
              }`}
            >
              <div className="flex items-start justify-between gap-2 mb-2.5">
                <div className="flex items-center gap-1.5">
                  {style.icon}
                  <span className={`text-[11px] font-mono px-2 py-0.5 rounded-full border ${style.badge}`}>
                    {style.label}
                  </span>
                </div>
                {isLoadingThis && (
                  <Loader2 className="h-4 w-4 animate-spin text-teal-600 dark:text-teal-400 shrink-0" />
                )}
              </div>

              <div>
                <div className="text-sm font-bold text-slate-900 dark:text-white leading-snug">{s.title}</div>
                <div className="mt-1 text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                  {s.description || style.subtitle}
                </div>
              </div>

              <div className="mt-3.5 flex items-center justify-between pt-2.5 border-t border-slate-100 dark:border-slate-700 text-xs font-semibold">
                <span className="text-slate-400 dark:text-slate-500 text-[11px] font-mono">Case {s.id.replace('SCENARIO_', '')}</span>
                <span className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-teal-50 dark:bg-teal-950/80 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 text-xs font-bold hover:bg-teal-100 dark:hover:bg-teal-900 transition-colors">
                  Load &amp; Run &rarr;
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default ScenarioSelector
