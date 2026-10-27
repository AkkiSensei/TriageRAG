import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type ScenarioDetail } from '@/lib/api'
import { AlertOctagon, HelpCircle, AlertTriangle, CheckCircle, Loader2, Zap } from 'lucide-react'

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

  const getVerdictDetails = (band: string) => {
    switch (band.toUpperCase()) {
      case 'BLOCK':
      case 'BLOCKED':
        return {
          icon: <AlertOctagon className="h-4 w-4 text-red-400 shrink-0" />,
          label: 'BLOCKED',
          subtitle: 'Fatal Sildenafil + Nitrate DDI',
          color: 'border-red-900/60 bg-red-950/40 text-red-300 hover:border-red-500/60 hover:bg-red-950/60',
          activeColor: 'border-red-500 bg-red-950/80 text-white shadow-lg shadow-red-950/50',
          badge: 'bg-red-500/20 text-red-300 border-red-500/40',
        }
      case 'HIGH':
        return {
          icon: <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />,
          label: 'HIGH ALERT',
          subtitle: 'Penicillin Ceftriaxone Anaphylaxis',
          color: 'border-amber-900/60 bg-amber-950/40 text-amber-300 hover:border-amber-500/60 hover:bg-amber-950/60',
          activeColor: 'border-amber-500 bg-amber-950/80 text-white shadow-lg shadow-amber-950/50',
          badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
        }
      case 'UNVERIFIED':
        return {
          icon: <HelpCircle className="h-4 w-4 text-purple-400 shrink-0" />,
          label: 'UNVERIFIED',
          subtitle: 'Missing Renal Vitals (Fail-Closed)',
          color: 'border-purple-900/60 bg-purple-950/40 text-purple-300 hover:border-purple-500/60 hover:bg-purple-950/60',
          activeColor: 'border-purple-500 bg-purple-950/80 text-white shadow-lg shadow-purple-950/50',
          badge: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
        }
      case 'CHECKED_CLEAR':
      case 'CLEAR':
      default:
        return {
          icon: <CheckCircle className="h-4 w-4 text-teal-400 shrink-0" />,
          label: 'CHECKED CLEAR',
          subtitle: 'Acute Asthma Salbutamol Inhalation',
          color: 'border-teal-900/60 bg-teal-950/40 text-teal-300 hover:border-teal-500/60 hover:bg-teal-950/60',
          activeColor: 'border-teal-500 bg-teal-950/80 text-white shadow-lg shadow-teal-950/50',
          badge: 'bg-teal-500/20 text-teal-300 border-teal-500/40',
        }
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-400">
        <Loader2 className="h-4 w-4 animate-spin text-teal-400" />
        <span>Loading reference triage scenarios...</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2.5 rounded-xl border border-slate-800 bg-slate-900/50 p-3.5 backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-200">
          <Zap className="h-3.5 w-3.5 text-amber-400" />
          <span>1-Click Clinical Showcase</span>
        </div>
        <span className="text-[11px] font-mono text-slate-400">
          Click any case to test live
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {scenarios?.map((s) => {
          const isLoadingThis = loadingScenarioId === s.id
          const isActive = activeScenarioId === s.id
          const details = getVerdictDetails(s.expected_verdict)

          return (
            <button
              key={s.id}
              type="button"
              onClick={() => handleSelect(s.id, true)}
              disabled={isLoadingThis}
              className={`group flex flex-col items-start gap-1 rounded-lg border p-2.5 text-left transition-all ${
                isActive ? details.activeColor : details.color
              }`}
            >
              <div className="flex w-full items-center justify-between">
                <div className="flex items-center gap-1.5 font-mono text-[11px] font-bold">
                  {isLoadingThis ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    details.icon
                  )}
                  <span>{details.label}</span>
                </div>
                {isActive && (
                  <span className="flex h-1.5 w-1.5 rounded-full bg-teal-400" />
                )}
              </div>
              <span className="text-xs font-semibold text-slate-100 line-clamp-1 group-hover:text-white">
                {s.title}
              </span>
              <span className="text-[10px] text-slate-400 line-clamp-1">
                {details.subtitle}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
