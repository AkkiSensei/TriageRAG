import React from 'react'
import { Activity, AlertCircle, Heart, Wind, Gauge, Brain, Thermometer, Droplets } from 'lucide-react'
import type { EngineReport } from '@/lib/api'

interface ScoreCardProps {
  score: NonNullable<EngineReport['score']>
}

export const ScoreCard: React.FC<ScoreCardProps> = ({ score }) => {
  const band = score.band || 'UNSCORED'
  let bandBadgeColor = 'border-slate-200 bg-slate-100 text-slate-700 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-300'
  let bandGlow = 'border-slate-200 dark:border-[#1e3840]'

  if (band === 'GREEN') {
    bandBadgeColor = 'border-teal-300 bg-teal-100/80 text-teal-900 dark:bg-teal-950/60 dark:border-teal-700 dark:text-teal-200 font-bold'
    bandGlow = 'border-teal-200 dark:border-teal-800/80'
  } else if (band === 'YELLOW') {
    bandBadgeColor = 'border-amber-300 bg-amber-100/80 text-amber-900 dark:bg-amber-950/60 dark:border-amber-700 dark:text-amber-200 font-bold'
    bandGlow = 'border-amber-200 dark:border-amber-800/80'
  } else if (band === 'ORANGE') {
    bandBadgeColor = 'border-orange-300 bg-orange-100/80 text-orange-900 dark:bg-orange-950/60 dark:border-orange-700 dark:text-orange-200 font-bold'
    bandGlow = 'border-orange-200 dark:border-orange-800/80'
  } else if (band === 'RED') {
    bandBadgeColor = 'border-rose-300 bg-rose-100/90 text-rose-950 dark:bg-rose-950/60 dark:border-rose-700 dark:text-rose-200 font-bold'
    bandGlow = 'border-rose-200 dark:border-rose-800/80'
  }

  const getMetricIcon = (metric: string) => {
    const m = metric.toLowerCase()
    if (m.includes('heart') || m.includes('pulse')) return <Heart className="h-3.5 w-3.5 text-coral-500" />
    if (m.includes('resp') || m.includes('o2') || m.includes('spo2')) return <Wind className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
    if (m.includes('bp') || m.includes('pressure')) return <Gauge className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400" />
    if (m.includes('temp')) return <Thermometer className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
    if (m.includes('glucose') || m.includes('sugar')) return <Droplets className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400" />
    if (m.includes('conscious') || m.includes('avpu') || m.includes('gcs')) return <Brain className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
    return <Activity className="h-3.5 w-3.5 text-teal-600 dark:text-teal-400" />
  }

  return (
    <div className={`rounded-3xl border ${bandGlow} bg-white dark:bg-[#132226] p-5 sm:p-6 shadow-soft transition-all`}>
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-[#1e3840] pb-3.5 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-100">
              {score.score_name} Scorecard
            </div>
            <div className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
              Deterministic Physiological Early Warning Stratification
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <span className={`px-3 py-1 rounded-full text-xs font-mono border shadow-soft-sm ${bandBadgeColor}`}>
            BAND: {band}
          </span>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-slate-50 dark:bg-[#0c1618] border border-slate-200 dark:border-[#1e3840]">
            <span className="text-[10px] uppercase font-bold text-slate-400 dark:text-slate-500">Total:</span>
            <span className="font-mono text-base font-extrabold text-slate-900 dark:text-slate-100">
              {score.total_score !== null && score.total_score !== undefined ? score.total_score : 'N/A'}
            </span>
          </div>
        </div>
      </div>

      {score.missing_vitals && score.missing_vitals.length > 0 && (
        <div className="mb-4 flex items-center gap-2.5 rounded-2xl border border-violet-200 dark:border-violet-800/60 bg-violet-50/80 dark:bg-violet-950/40 p-3 text-xs text-violet-900 dark:text-violet-200">
          <AlertCircle className="h-4 w-4 shrink-0 text-violet-600 dark:text-violet-400" />
          <span className="font-medium">
            Incomplete vitals for full score: <strong>{score.missing_vitals.join(', ')}</strong> (Score capped or unscored)
          </span>
        </div>
      )}

      {score.subscores && Object.keys(score.subscores).length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5 pt-1 text-xs">
          {Object.entries(score.subscores).map(([metric, val]) => (
            <div
              key={metric}
              className="flex items-center justify-between rounded-xl bg-slate-50/90 dark:bg-[#0c1618] px-3 py-2 border border-slate-200/80 dark:border-[#1e3840] hover:bg-slate-100/60 dark:hover:bg-[#1a2d33] transition-colors"
            >
              <div className="flex items-center gap-2 truncate pr-1">
                {getMetricIcon(metric)}
                <span className="text-slate-600 dark:text-slate-300 capitalize truncate text-[11px] font-medium">
                  {metric.replace(/_/g, ' ')}
                </span>
              </div>
              <span className={`font-mono font-bold text-xs ${Number(val) > 0 ? 'text-coral-600 dark:text-coral-400 font-extrabold' : 'text-slate-500 dark:text-slate-400'}`}>
                +{val}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ScoreCard
