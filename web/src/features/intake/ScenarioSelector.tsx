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
          icon: <AlertOctagon className="h-4 w-4 text-red-600 shrink-0" />,
          label: 'BLOCKED',
          subtitle: 'Fatal Sildenafil + Nitrate DDI',
          color: 'border-red-200 bg-red-50/60 text-red-900 hover:border-red-300 hover:bg-red-50',
          activeColor: 'border-red-500 bg-red-50 text-red-950 font-bold ring-2 ring-red-500/20 shadow-sm',
          badge: 'bg-red-100 text-red-800 border-red-200',
        }
      case 'HIGH':
        return {
          icon: <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />,
          label: 'HIGH ALERT',
          subtitle: 'Penicillin Ceftriaxone Anaphylaxis',
          color: 'border-amber-200 bg-amber-50/60 text-amber-900 hover:border-amber-300 hover:bg-amber-50',
          activeColor: 'border-amber-500 bg-amber-50 text-amber-950 font-bold ring-2 ring-amber-500/20 shadow-sm',
          badge: 'bg-amber-100 text-amber-800 border-amber-200',
        }
      case 'UNVERIFIED':
        return {
          icon: <HelpCircle className="h-4 w-4 text-purple-600 shrink-0" />,
          label: 'UNVERIFIED',
          subtitle: 'Missing Renal Vitals (Fail-Closed)',
          color: 'border-purple-200 bg-purple-50/60 text-purple-900 hover:border-purple-300 hover:bg-purple-50',
          activeColor: 'border-purple-500 bg-purple-50 text-purple-950 font-bold ring-2 ring-purple-500/20 shadow-sm',
          badge: 'bg-purple-100 text-purple-800 border-purple-200',
        }
      case 'CHECKED_CLEAR':
      case 'CLEAR':
      default:
        return {
          icon: <CheckCircle className="h-4 w-4 text-[#2D6A4F] shrink-0" />,
          label: 'CHECKED CLEAR',
          subtitle: 'Acute Asthma Salbutamol Inhalation',
          color: 'border-[#A5D6A7] bg-[#E8F5E9]/60 text-[#1B4D39] hover:border-[#2D6A4F] hover:bg-[#E8F5E9]',
          activeColor: 'border-[#2D6A4F] bg-[#E8F5E9] text-[#1B4D39] font-bold ring-2 ring-[#2D6A4F]/25 shadow-sm',
          badge: 'bg-[#E8F5E9] text-[#1B4D39] border-[#A5D6A7]',
        }
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-[#E1E7E1] bg-white p-3 text-xs text-[#5C6B64]">
        <Loader2 className="h-4 w-4 animate-spin text-[#2D6A4F]" />
        <span>Loading reference triage scenarios...</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2.5 rounded-xl border border-[#E1E7E1] bg-white p-3.5 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#1A2421]">
          <Zap className="h-3.5 w-3.5 text-amber-500" />
          <span>1-Click Clinical Showcase</span>
        </div>
        <span className="text-[11px] font-mono text-[#5C6B64]">
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
                  <span className="flex h-1.5 w-1.5 rounded-full bg-[#2D6A4F]" />
                )}
              </div>
              <span className="text-xs font-semibold text-[#1A2421] line-clamp-1">
                {s.title}
              </span>
              <span className="text-[10px] text-[#5C6B64] line-clamp-1">
                {details.subtitle}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

