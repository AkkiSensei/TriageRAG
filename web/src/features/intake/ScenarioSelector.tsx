import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type ScenarioDetail } from '@/lib/api'
import { AlertOctagon, HelpCircle, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react'

interface ScenarioSelectorProps {
  onSelectScenario: (scenario: ScenarioDetail) => void
  loadingScenarioId?: string | null
}

export const ScenarioSelector: React.FC<ScenarioSelectorProps> = ({
  onSelectScenario,
  loadingScenarioId,
}) => {
  const { data: scenarios, isLoading } = useQuery({
    queryKey: ['scenarios'],
    queryFn: api.getScenarios,
  })

  const handleSelect = async (id: string) => {
    try {
      const detail = await api.getScenario(id)
      onSelectScenario(detail)
    } catch (err) {
      console.error('Failed to load scenario:', err)
    }
  }

  const getBadgeIcon = (band: string) => {
    switch (band.toUpperCase()) {
      case 'BLOCK':
      case 'BLOCKED':
        return <AlertOctagon className="h-3.5 w-3.5 text-red-400" />
      case 'UNVERIFIED':
        return <HelpCircle className="h-3.5 w-3.5 text-purple-400" />
      case 'HIGH':
        return <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
      case 'CHECKED_CLEAR':
      case 'CLEAR':
      default:
        return <CheckCircle className="h-3.5 w-3.5 text-teal-400" />
    }
  }

  const getBadgeColor = (band: string) => {
    switch (band.toUpperCase()) {
      case 'BLOCK':
      case 'BLOCKED':
        return 'border-red-900/60 bg-red-950/40 text-red-300 hover:bg-red-900/30'
      case 'UNVERIFIED':
        return 'border-purple-900/60 bg-purple-950/40 text-purple-300 hover:bg-purple-900/30'
      case 'HIGH':
        return 'border-amber-900/60 bg-amber-950/40 text-amber-300 hover:bg-amber-900/30'
      case 'CHECKED_CLEAR':
      case 'CLEAR':
      default:
        return 'border-teal-900/60 bg-teal-950/40 text-teal-300 hover:bg-teal-900/30'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-400">
        <Loader2 className="h-4 w-4 animate-spin text-teal-400" />
        <span>Loading reference triage scenarios...</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
          Load Pre-Engineered Scenario
        </span>
        <span className="text-[10px] font-mono text-slate-400">Golden Reference Cases</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {scenarios?.map((s) => {
          const isLoadingThis = loadingScenarioId === s.id
          return (
            <button
              key={s.id}
              onClick={() => handleSelect(s.id)}
              disabled={isLoadingThis}
              className={`flex flex-col items-start gap-1 rounded-lg border p-2.5 text-left transition-all ${getBadgeColor(
                s.expected_verdict
              )}`}
            >
              <div className="flex items-center gap-1.5 font-mono text-[11px] font-bold">
                {isLoadingThis ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : getBadgeIcon(s.expected_verdict)}
                <span>{s.expected_verdict}</span>
              </div>
              <span className="text-xs font-medium text-slate-100 line-clamp-1">{s.title}</span>
              <span className="text-[10px] text-slate-400 line-clamp-1">{s.description}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
