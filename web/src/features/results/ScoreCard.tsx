import React from 'react'
import { Activity, AlertCircle } from 'lucide-react'
import type { EngineReport } from '@/lib/api'

interface ScoreCardProps {
  score: NonNullable<EngineReport['score']>
}

export const ScoreCard: React.FC<ScoreCardProps> = ({ score }) => {
  const band = score.band || 'UNSCORED'
  let bandBadgeColor = 'border-slate-700 bg-slate-800 text-slate-300'
  if (band === 'GREEN') bandBadgeColor = 'border-teal-800 bg-teal-950/60 text-teal-300'
  if (band === 'YELLOW') bandBadgeColor = 'border-amber-800 bg-amber-950/60 text-amber-300'
  if (band === 'ORANGE') bandBadgeColor = 'border-orange-800 bg-orange-950/60 text-orange-300'
  if (band === 'RED') bandBadgeColor = 'border-red-800 bg-red-950/60 text-red-300 font-bold'

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-teal-400" />
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-200">
            {score.score_name} Early Warning Score
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-mono border ${bandBadgeColor}`}>
            BAND: {band}
          </span>
          <span className="font-mono text-base font-bold text-white px-2 py-0.5 rounded bg-slate-950 border border-slate-800">
            {score.total_score !== null && score.total_score !== undefined ? score.total_score : 'N/A'}
          </span>
        </div>
      </div>

      {score.missing_vitals && score.missing_vitals.length > 0 && (
        <div className="mb-3 flex items-center gap-2 rounded-md border border-purple-900/50 bg-purple-950/30 p-2 text-[11px] text-purple-300">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span>Incomplete vitals for scoring: {score.missing_vitals.join(', ')}</span>
        </div>
      )}

      {score.subscores && Object.keys(score.subscores).length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[11px]">
          {Object.entries(score.subscores).map(([metric, val]) => (
            <div key={metric} className="flex items-center justify-between rounded bg-slate-950/80 px-2.5 py-1.5 border border-slate-800/80">
              <span className="text-slate-400 capitalize">{metric.replace(/_/g, ' ')}:</span>
              <span className="font-mono font-bold text-slate-200">+{val}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
