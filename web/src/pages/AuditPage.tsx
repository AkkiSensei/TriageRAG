import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type AuditEntryDto } from '@/lib/api'
import {
  Hash,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Clock,
  FileCheck2,
  RefreshCw,
} from 'lucide-react'

export const AuditPage: React.FC = () => {
  const [isVerifying, setIsVerifying] = useState(false)
  const [verificationResult, setVerificationResult] = useState<{
    valid: boolean
    first_bad_index?: number | string | null
  } | null>(null)

  const {
    data: entries,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['audit-entries'],
    queryFn: () => api.getAuditEntries(50),
  })

  const handleVerifyChain = async () => {
    setIsVerifying(true)
    try {
      const res = await api.verifyAuditChain()
      setVerificationResult(res)
    } catch (err) {
      console.error('Audit verification error:', err)
      setVerificationResult({ valid: false })
    } finally {
      setIsVerifying(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-2 rounded-3xl border border-[#d9e8e6] dark:border-[#1e3840] bg-gradient-to-r from-teal-50/40 dark:from-teal-950/30 via-white dark:via-[#132226] to-white dark:to-[#132226] p-5 sm:p-6 shadow-soft">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <Hash className="h-4 w-4" />
          </div>
          <span className="text-xs font-mono uppercase tracking-widest text-teal-800 dark:text-teal-300 font-bold">
            Tamper-Evident Governance
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 font-semibold border border-teal-200 dark:border-teal-800">
            SHA-256 Merkle Chain
          </span>
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
          Cryptographic Clinical Audit Log
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-2xl leading-relaxed">
          Every triage execution, patient hash, rule check, override, and retrieval query is permanently sealed
          into an append-only cryptographic hash chain for hospital legal governance.
        </p>
      </div>

      {/* Verify Chain Control Card */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 shadow-soft">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              Cryptographic Integrity Verification
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Verify that no past triage records or overrides have been modified or re-ordered.
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {verificationResult && (
            <span
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-mono font-bold border shadow-soft-sm ${
                verificationResult.valid
                  ? 'bg-teal-100 dark:bg-teal-950/70 text-teal-900 dark:text-teal-200 border-teal-300 dark:border-teal-700'
                  : 'bg-rose-100 dark:bg-rose-950/70 text-rose-900 dark:text-rose-200 border-rose-300 dark:border-rose-700'
              }`}
            >
              {verificationResult.valid ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5 text-teal-700 dark:text-teal-400" />
                  <span>Chain Valid (100% Intact)</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="h-3.5 w-3.5 text-rose-700 dark:text-rose-400" />
                  <span>Broken Chain (Index #{verificationResult.first_bad_index})</span>
                </>
              )}
            </span>
          )}

          <button
            type="button"
            onClick={handleVerifyChain}
            disabled={isVerifying}
            className="flex items-center gap-2 rounded-xl bg-teal-700 hover:bg-teal-800 px-5 py-2 text-xs font-bold text-white shadow-soft transition-all disabled:opacity-50"
          >
            {isVerifying ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <FileCheck2 className="h-3.5 w-3.5" />
            )}
            <span>Verify Merkle Chain</span>
          </button>
        </div>
      </div>

      {/* Entries List */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-[#1e3840]">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-100">
            Recent Audit Blocks ({entries?.length || 0})
          </span>
          <button
            type="button"
            onClick={() => refetch()}
            className="flex items-center gap-1 text-[11px] font-mono text-teal-700 dark:text-teal-400 hover:text-teal-900 dark:hover:text-teal-200 font-semibold"
          >
            <RefreshCw className="h-3 w-3" /> Refresh
          </button>
        </div>

        {isLoading && (
          <div className="flex flex-col items-center justify-center p-12 text-slate-500 dark:text-slate-400">
            <Loader2 className="h-8 w-8 animate-spin text-teal-600 dark:text-teal-400 mb-2" />
            <span className="text-xs font-medium">Loading cryptographic audit trail...</span>
          </div>
        )}

        {!isLoading && (!entries || entries.length === 0) && (
          <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-10 text-center text-xs text-slate-400 dark:text-slate-500 shadow-soft">
            No audit records created yet. Run a triage evaluation on the Intake Station to generate the first block.
          </div>
        )}

        {!isLoading &&
          entries?.map((entry: AuditEntryDto) => (
            <div
              key={entry.sequence_number}
              className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 shadow-soft hover:border-teal-300 dark:hover:border-teal-700 transition-all text-xs font-mono"
            >
              <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-800 dark:text-teal-300 font-bold border border-teal-200 dark:border-teal-800 text-[11px]">
                    #{entry.sequence_number}
                  </span>
                  <span className="font-bold text-slate-900 dark:text-slate-100 text-xs">
                    Verdict: <strong className="text-teal-700 dark:text-teal-400">{entry.verdict}</strong>
                  </span>
                </div>

                <div className="flex items-center gap-2 text-slate-400 dark:text-slate-500 text-[11px]">
                  <Clock className="h-3 w-3" />
                  <span>{entry.timestamp_iso || 'Timestamp UTC'}</span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 my-2 text-[11px] text-slate-600 dark:text-slate-300">
                <div>
                  <span className="text-slate-400 dark:text-slate-500">Patient Hash: </span>
                  <span className="font-bold text-slate-800 dark:text-slate-200 select-all">
                    {entry.patient_hash.slice(0, 24)}...
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 dark:text-slate-500">Ruleset Version: </span>
                  <span className="text-slate-800 dark:text-slate-200">{entry.ruleset_version}</span>
                </div>
              </div>

              <div className="mt-3 flex flex-col gap-1 rounded-xl bg-slate-50 dark:bg-[#0c1618] border border-slate-200 dark:border-[#1e3840] p-3 text-[10px] text-slate-500 dark:text-slate-400">
                <div className="flex items-center justify-between">
                  <span>Record SHA-256 Hash:</span>
                  <span className="font-bold text-teal-800 dark:text-teal-300 select-all">{entry.record_hash}</span>
                </div>
                {entry.previous_hash && (
                  <div className="flex items-center justify-between">
                    <span>Previous Block Hash:</span>
                    <span className="text-slate-400 dark:text-slate-500 select-all">{entry.previous_hash}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
      </div>
    </div>
  )
}

export default AuditPage
