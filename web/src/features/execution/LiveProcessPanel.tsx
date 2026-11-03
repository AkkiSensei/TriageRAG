/**
 * Live Evidence-Backed Process Graph & Real-Time Activity Feed (ADR 0017).
 *
 * Safety Properties (Rule R1, Rule R2, Rule R7, Rule R11):
 * 1. Software execution observability only: academic visualization of deterministic pipeline nodes.
 * 2. Real-time event reflection: strictly updates from actual backend lifecycle SSE messages.
 *    Zero timers, zero artificial progression, zero fabricated delay.
 * 3. Privacy allowlist: safe summaries contain only operation counts/status codes,
 *    strictly forbidding patient identifiers, vitals, drugs, allergies, complaint narratives,
 *    and exception tracebacks.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Cpu,
  ListTree,
  RotateCw,
  ShieldCheck,
  SkipForward,
  Terminal,
  XCircle,
} from 'lucide-react'
import type { TriageLifecycleEvent, StageStatus } from '@/types/execution'
import { PROCESS_STAGES, type ProcessStageDefinition } from '@/types/execution'

interface LiveProcessPanelProps {
  events: TriageLifecycleEvent[]
  isLoading: boolean
  className?: string
  onNavigateToReport?: () => void
}

export const LiveProcessPanel: React.FC<LiveProcessPanelProps> = ({
  events,
  isLoading,
  className = '',
  onNavigateToReport,
}) => {
  const [activeTab, setActiveTab] = useState<'graph' | 'feed'>('graph')
  const feedEndRef = useRef<HTMLDivElement>(null)

  const isRunComplete = useMemo(() => {
    return events.some((e) => e.event_type === 'run.completed')
  }, [events])

  // Compute live stage status map derived strictly from emitted events
  const stageStatusMap = useMemo(() => {
    const map: Record<string, { status: StageStatus; summary: string; timestamp?: string }> = {}

    // Initialize all defined stages to 'pending'
    for (const stage of PROCESS_STAGES) {
      map[stage.id] = { status: 'pending', summary: '' }
    }

    // Process events chronologically
    for (const ev of events) {
      // Find matching stage definition that covers this backend stage
      const matchingDef = PROCESS_STAGES.find((s) => s.backendStages.includes(ev.stage))
      if (!matchingDef) continue

      if (ev.event_type === 'stage.started') {
        map[matchingDef.id] = {
          status: 'running',
          summary: ev.safe_summary,
          timestamp: ev.timestamp,
        }
      } else if (ev.event_type === 'stage.completed') {
        map[matchingDef.id] = {
          status: 'completed',
          summary: ev.safe_summary,
          timestamp: ev.timestamp,
        }
      } else if (ev.event_type === 'stage.skipped') {
        // If it's a multi-branch stage (like seal or draft), don't mark as skipped unless currently pending
        if (matchingDef.id === 'disposition_seal' || matchingDef.id === 'draft_plan') {
          if (map[matchingDef.id].status === 'pending') {
            map[matchingDef.id] = {
              status: 'skipped',
              summary: ev.safe_summary,
              timestamp: ev.timestamp,
            }
          }
        } else {
          map[matchingDef.id] = {
            status: 'skipped',
            summary: ev.safe_summary,
            timestamp: ev.timestamp,
          }
        }
      } else if (ev.event_type === 'stage.failed') {
        map[matchingDef.id] = {
          status: 'failed',
          summary: ev.safe_summary,
          timestamp: ev.timestamp,
        }
      }
    }

    return map
  }, [events])

  // Count metrics
  const completedStages = useMemo(() => {
    return Object.values(stageStatusMap).filter((s) => s.status === 'completed').length
  }, [stageStatusMap])

  // Auto-scroll activity feed to latest event
  useEffect(() => {
    if (activeTab === 'feed' && feedEndRef.current && typeof feedEndRef.current.scrollIntoView === 'function') {
      feedEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events, activeTab])

  const formatTime = (isoString?: string) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      const base = d.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
      const ms = String(d.getMilliseconds()).padStart(3, '0')
      return `${base}.${ms}`
    } catch {
      return ''
    }
  }

  const renderStatusBadge = (status: StageStatus) => {
    switch (status) {
      case 'running':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 border border-sky-300 dark:border-sky-800 animate-pulse">
            <RotateCw className="w-3 h-3 animate-spin" />
            Executing
          </span>
        )
      case 'completed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
            <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
            Done
          </span>
        )
      case 'skipped':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
            <SkipForward className="w-3 h-3 text-amber-600 dark:text-amber-400" />
            Skipped
          </span>
        )
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300 dark:border-rose-800">
            <XCircle className="w-3 h-3 text-rose-600 dark:text-rose-400" />
            Failed
          </span>
        )
      case 'pending':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
            <Clock className="w-3 h-3 text-slate-400" />
            Pending
          </span>
        )
    }
  }

  return (
    <div
      data-testid="live-process-panel"
      className={`flex flex-col rounded-3xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-soft overflow-hidden ${className}`}
    >
      {/* Header bar */}
      <div className="flex flex-col gap-2 p-4 sm:p-5 border-b border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/80">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/80 text-teal-700 dark:text-teal-300">
              <Cpu className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                Live Execution Process Graph
              </h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Deterministic LangGraph State Machine (ADR 0017)
              </p>
            </div>
          </div>

          {/* Mode Badge */}
          <div className="flex items-center gap-2">
            {isLoading ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-sky-100 text-sky-800 dark:bg-sky-950/80 dark:text-sky-300 border border-sky-300 dark:border-sky-800">
                <span className="h-2 w-2 rounded-full bg-sky-500 animate-ping" />
                Active Run
              </span>
            ) : events.length > 0 ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                Completed
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                Standby
              </span>
            )}
          </div>
        </div>

        {/* View Switcher & Progress bar */}
        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center bg-slate-200/80 dark:bg-slate-700/80 p-0.5 rounded-xl text-xs font-medium">
            <button
              type="button"
              onClick={() => setActiveTab('graph')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-colors ${
                activeTab === 'graph'
                  ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-soft-sm font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <ListTree className="w-3.5 h-3.5" />
              Process Graph
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('feed')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-colors ${
                activeTab === 'feed'
                  ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-soft-sm font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              Activity Feed ({events.length})
            </button>
          </div>

          <div className="text-right text-[11px] text-slate-500 dark:text-slate-400">
            <span className="font-semibold text-slate-800 dark:text-slate-200">
              {completedStages} of {PROCESS_STAGES.length}
            </span>{' '}
            stages finished
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 p-4 sm:p-5 overflow-y-auto max-h-[540px]">
        {activeTab === 'graph' ? (
          <div className="space-y-3">
            {PROCESS_STAGES.map((stage: ProcessStageDefinition, idx: number) => {
              const info = stageStatusMap[stage.id] || { status: 'pending', summary: '' }
              const isCurrent = info.status === 'running'
              const isFinished = info.status === 'completed'
              const isSkipped = info.status === 'skipped'
              const isFailed = info.status === 'failed'

              let borderColor = 'border-slate-200 dark:border-slate-700/80 bg-white dark:bg-slate-800/60'
              if (isCurrent) {
                borderColor = 'border-sky-400 dark:border-sky-600 bg-sky-50/50 dark:bg-sky-950/20 shadow-soft-sm ring-1 ring-sky-300'
              } else if (isFinished) {
                borderColor = 'border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/20 dark:bg-emerald-950/10'
              } else if (isSkipped) {
                borderColor = 'border-amber-200 dark:border-amber-800/60 bg-amber-50/20 dark:bg-amber-950/10'
              } else if (isFailed) {
                borderColor = 'border-rose-300 dark:border-rose-700 bg-rose-50/30 dark:bg-rose-950/20'
              }

              return (
                <div
                  key={stage.id}
                  data-testid={`stage-card-${stage.id}`}
                  className={`rounded-2xl border p-3.5 transition-all duration-200 ${borderColor}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5">
                      <div
                        className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${
                          isFinished
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                            : isCurrent
                            ? 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 animate-pulse'
                            : isSkipped
                            ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                            : isFailed
                            ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                            : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400'
                        }`}
                      >
                        {idx + 1}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                            {stage.label}
                          </h4>
                        </div>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-snug mt-0.5">
                          {stage.description}
                        </p>
                      </div>
                    </div>

                    <div className="shrink-0">{renderStatusBadge(info.status)}</div>
                  </div>

                  {/* Real Safe Summary from event emission */}
                  {info.summary && (
                    <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-slate-700/50 flex items-start gap-1.5 text-[11px] text-slate-700 dark:text-slate-300 font-mono">
                      <span className="text-teal-600 dark:text-teal-400 font-bold">›</span>
                      <span className="break-words">{info.summary}</span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          /* Real-Time Activity Feed */
          <div className="space-y-2">
            {events.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 px-4 text-center text-slate-400 dark:text-slate-500">
                <Terminal className="h-8 w-8 mb-2 stroke-1 text-slate-300 dark:text-slate-600" />
                <p className="text-xs font-medium">No live events emitted yet.</p>
                <p className="text-[11px] mt-1 max-w-xs">
                  Submit patient details to stream real execution events directly from the LangGraph engine.
                </p>
              </div>
            ) : (
              events.map((ev, i) => (
                <div
                  key={`${ev.request_id}-${ev.sequence}-${i}`}
                  data-testid="feed-event-item"
                  className="flex items-start gap-2.5 p-2.5 rounded-xl border border-slate-100 dark:border-slate-700/60 bg-slate-50/50 dark:bg-slate-800/40 text-xs font-mono"
                >
                  <span className="text-[10px] font-bold text-slate-400 px-1 py-0.5 rounded bg-slate-200/60 dark:bg-slate-700/60">
                    #{String(ev.sequence).padStart(2, '0')}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span
                        className={`text-[10px] uppercase font-bold px-1.5 py-0.2 rounded ${
                          ev.event_type === 'stage.completed' || ev.event_type === 'run.completed'
                            ? 'text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/60'
                            : ev.event_type === 'stage.started'
                            ? 'text-sky-700 dark:text-sky-300 bg-sky-50 dark:bg-sky-950/60'
                            : ev.event_type === 'stage.skipped'
                            ? 'text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/60'
                            : 'text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/60'
                        }`}
                      >
                        {ev.stage}
                      </span>
                      <span className="text-[10px] text-slate-400">{formatTime(ev.timestamp)}</span>
                    </div>
                    <p className="text-[11px] text-slate-700 dark:text-slate-300 mt-1 break-words">
                      {ev.safe_summary}
                    </p>
                  </div>
                </div>
              ))
            )}
            <div ref={feedEndRef} />
          </div>
        )}
      </div>

      {/* Academic Safety / Disclaimer Footer */}
      <div className="p-3 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/90 flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-left">
        <p className="text-[10px] text-slate-500 dark:text-slate-400 font-mono">
          Academic Observability Only. Driven by LangGraph State Machine. Not a clinical device.
        </p>
        {onNavigateToReport && isRunComplete && !isLoading && (
          <button
            type="button"
            onClick={onNavigateToReport}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold text-white bg-teal-600 hover:bg-teal-700 shadow-soft-sm transition-colors shrink-0 cursor-pointer"
          >
            <span>Proceed to Results</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        )}
      </div>
    </div>
  )
}
