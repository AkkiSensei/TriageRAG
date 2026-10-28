import React from 'react'
import { Activity, AlertCircle } from 'lucide-react'
import type { EngineReport } from '@/lib/api'

interface ScoreCardProps {
  score: NonNullable<EngineReport['score']>
}

export const ScoreCard: React.FC<ScoreCardProps> = ({ score }) => {
  const band = score.band || 'UNSCORED'
  let bandBadgeColor = 'border-[#E1E7E1] bg-[#F4F6F4] text-[#5C6B64]'
  if (band === 'GREEN') bandBadgeColor = 'border-[#A5D6A7] bg-[#E8F5E9] text-[#2E7D32] font-bold'
  if (band === 'YELLOW') bandBadgeColor = 'border-amber-300 bg-amber-50 text-amber-800 font-bold'
  if (band === 'ORANGE') bandBadgeColor = 'border-orange-300 bg-orange-50 text-orange-800 font-bold'
  if (band === 'RED') bandBadgeColor = 'border-red-300 bg-red-50 text-red-800 font-bold'

  return (
    <div className="rounded-xl border border-[#E1E7E1] bg-white p-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#E1E7E1] pb-3 mb-3">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-[#2D6A4F]" />
          <span className="text-xs font-bold uppercase tracking-wider text-[#1A2421]">
            {score.score_name} Early Warning Score
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-mono border ${bandBadgeColor}`}>
            BAND: {band}
          </span>
          <span className="font-mono text-base font-bold text-[#1A2421] px-2.5 py-0.5 rounded-lg bg-[#F4F6F4] border border-[#E1E7E1]">
            {score.total_score !== null && score.total_score !== undefined ? score.total_score : 'N/A'}
          </span>
        </div>
      </div>

      {score.missing_vitals && score.missing_vitals.length > 0 && (
        <div className="mb-3 flex items-center gap-2 rounded-lg border border-purple-200 bg-purple-50 p-2 text-[11px] text-purple-900">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 text-purple-600" />
          <span>Incomplete vitals for scoring: {score.missing_vitals.join(', ')}</span>
        </div>
      )}

      {score.subscores && Object.keys(score.subscores).length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[11px]">
          {Object.entries(score.subscores).map(([metric, val]) => (
            <div key={metric} className="flex items-center justify-between rounded-lg bg-[#F4F6F4] px-2.5 py-1.5 border border-[#E1E7E1]">
              <span className="text-[#5C6B64] capitalize">{metric.replace(/_/g, ' ')}:</span>
              <span className="font-mono font-bold text-[#1A2421]">+{val}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

