import React, { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api, type AuditVerifyResponse, type AuditEntryDto } from '@/lib/api'
import { Hash, Link2, AlertOctagon, CheckCircle2, RefreshCw, KeyRound } from 'lucide-react'
import { SplitText, BlurText, SpotlightCard } from '@/components/reactbits'

export const AuditPage: React.FC = () => {
  const [verificationResult, setVerificationResult] = useState<AuditVerifyResponse | null>(null)

  const { data: entries, isLoading, refetch } = useQuery({
    queryKey: ['audit-entries'],
    queryFn: () => api.getAuditEntries(100),
  })

  const verifyMutation = useMutation({
    mutationFn: api.verifyAuditChain,
    onSuccess: (data) => setVerificationResult(data),
  })

  const auditEntries = entries || []

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            <SplitText text="Cryptographic Audit Trail" />
          </h1>
          <div className="mt-1 text-sm text-slate-400">
            <BlurText text="Inspect SHA-256 hash chains of all clinical evaluations, override decisions, and integrity verification." />
          </div>
        </div>

        {/* Verify Hash Chain Button */}
        <button
          type="button"
          onClick={() => verifyMutation.mutate()}
          disabled={verifyMutation.isPending}
          className="flex items-center gap-2 rounded-lg bg-teal-500 hover:bg-teal-400 px-4 py-2 text-xs font-bold text-slate-950 shadow-lg shadow-teal-500/20 transition-all disabled:opacity-50"
        >
          {verifyMutation.isPending ? (
            <>
              <RefreshCw className="h-4 w-4 animate-spin" />
              <span>Verifying SHA-256 Chain...</span>
            </>
          ) : (
            <>
              <KeyRound className="h-4 w-4" />
              <span>Verify Audit Hash Chain</span>
            </>
          )}
        </button>
      </div>

      {/* Verification Status Banner */}
      {verificationResult && (
        <div
          className={`mb-8 rounded-xl border-2 p-4 ${
            verificationResult.valid
              ? 'border-teal-500/60 bg-teal-950/40 text-teal-200'
              : 'border-red-500/70 bg-red-950/40 text-red-200 shadow-[0_0_20px_rgba(239,68,68,0.25)]'
          }`}
        >
          <div className="flex items-center gap-3">
            {verificationResult.valid ? (
              <CheckCircle2 className="h-6 w-6 text-teal-400 shrink-0" />
            ) : (
              <AlertOctagon className="h-6 w-6 text-red-400 shrink-0" />
            )}
            <div>
              <div className="text-sm font-bold uppercase tracking-wide font-mono">
                {verificationResult.valid
                  ? 'Cryptographic Audit Chain Intact: Zero Tampering Detected'
                  : 'INTEGRITY BREACH: Audit Hash Chain Broken'}
              </div>
              <p className="text-xs mt-0.5 text-slate-300">
                {verificationResult.valid
                  ? `Every record hash matches its pre-image and validly links to its parent previous_hash.`
                  : `Hash mismatch at sequence index: ${verificationResult.first_bad_index ?? 'Unknown'}`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Audit Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <SpotlightCard className="border-slate-800 bg-slate-900/60 p-4">
          <div className="text-xs uppercase text-slate-400 font-mono">Logged Decisions</div>
          <div className="mt-1 text-2xl font-bold text-white font-mono">{auditEntries.length}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Append-only audit blocks</div>
        </SpotlightCard>

        <SpotlightCard className="border-slate-800 bg-slate-900/60 p-4">
          <div className="text-xs uppercase text-slate-400 font-mono">Hash Function</div>
          <div className="mt-1 text-2xl font-bold text-teal-400 font-mono">SHA-256</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Canonical JSON serialization</div>
        </SpotlightCard>

        <SpotlightCard className="border-slate-800 bg-slate-900/60 p-4">
          <div className="text-xs uppercase text-slate-400 font-mono">Chain Architecture</div>
          <div className="mt-1 text-2xl font-bold text-teal-400 font-mono">Merkle Link</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Parent-hash anchoring</div>
        </SpotlightCard>
      </div>

      {/* Audit Entries List */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Hash className="h-4 w-4 text-teal-400" />
            <h3 className="text-sm font-semibold text-slate-200">Audit Blocks ({auditEntries.length})</h3>
          </div>
          <button
            onClick={() => refetch()}
            className="text-xs text-teal-400 hover:text-teal-300 font-mono flex items-center gap-1"
          >
            <RefreshCw className="h-3 w-3" /> Refresh Log
          </button>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-xs text-slate-400">Loading audit log entries...</div>
        ) : auditEntries.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            No audit records created yet. Run a triage evaluation from the Console or Red-Team Lab.
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {auditEntries.map((entry: AuditEntryDto) => (
              <div
                key={entry.sequence_number}
                className="rounded-lg border border-slate-800 bg-slate-950 p-4 flex flex-col gap-2 font-mono text-xs"
              >
                <div className="flex items-center justify-between flex-wrap gap-2 border-b border-slate-900 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-teal-400">Block #{entry.sequence_number}</span>
                    <span className="text-[10px] text-slate-400">{entry.timestamp_iso}</span>
                  </div>
                  <span className="rounded bg-slate-900 border border-slate-800 px-2 py-0.5 text-[10px] text-slate-300 font-bold uppercase">
                    Verdict: {entry.verdict}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px] pt-1">
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase">Record Hash (SHA-256):</span>
                    <span className="text-slate-200 select-all break-all">{entry.record_hash}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase flex items-center gap-1">
                      <Link2 className="h-3 w-3 text-teal-400" />
                      <span>Previous Block Hash:</span>
                    </span>
                    <span className="text-slate-400 select-all break-all">{entry.previous_hash}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between flex-wrap gap-2 pt-2 border-t border-slate-900 text-[10px] text-slate-400">
                  <span>Patient Hash: {entry.patient_hash.slice(0, 16)}...</span>
                  <span>Ruleset: v{entry.ruleset_version}</span>
                  <span>Formulary: v{entry.formulary_version}</span>
                  <span>Alerts: {entry.alert_ids?.length ?? 0}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
