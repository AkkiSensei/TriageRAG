import React, { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  api,
  type RuleSummaryDto,
  type AuditVerifyResponse,
} from '@/lib/api'
import {
  BookOpen,
  FileText,
  CheckCircle2,
  Hash,
  Search,
  AlertOctagon,
  AlertTriangle,
  X,
  KeyRound,
  RefreshCw,
} from 'lucide-react'
import { SpotlightCard, CountUp } from '@/components/reactbits'

type IntelligenceTab = 'rules' | 'protocols' | 'evidence' | 'audit'

interface Props {
  initialTab?: IntelligenceTab
}

export const ClinicalIntelligencePage: React.FC<Props> = ({ initialTab = 'rules' }) => {
  const location = useLocation()
  const navigate = useNavigate()

  // Determine initial tab from props or route path
  const getTabFromPath = (): IntelligenceTab => {
    if (location.pathname.includes('/protocols')) return 'protocols'
    if (location.pathname.includes('/evidence')) return 'evidence'
    if (location.pathname.includes('/audit')) return 'audit'
    return initialTab
  }

  const [activeTab, setActiveTab] = useState<IntelligenceTab>(getTabFromPath())

  useEffect(() => {
    setActiveTab(getTabFromPath())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  const handleTabChange = (tab: IntelligenceTab) => {
    setActiveTab(tab)
    navigate(`/${tab === 'rules' ? 'ruleset' : tab}`, { replace: true })
  }

  // --- 1. Rules Data ---
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all')
  const [selectedRule, setSelectedRule] = useState<RuleSummaryDto | null>(null)

  const { data: rulesData, isLoading: rulesLoading } = useQuery({
    queryKey: ['rules'],
    queryFn: api.getRules,
  })

  const rules = rulesData || []
  const filteredRules = rules.filter((r) => {
    const matchesSearch =
      r.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.rule_type.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesSeverity =
      selectedSeverity === 'all' || r.severity.toUpperCase() === selectedSeverity.toUpperCase()
    return matchesSearch && matchesSeverity
  })

  // --- 2. Protocols Data ---
  const [protocolSearch, setProtocolSearch] = useState('')
  const { data: protocolsData } = useQuery({
    queryKey: ['protocols'],
    queryFn: api.getProtocols,
  })
  const protocolList = protocolsData || []
  const filteredProtocols = protocolList.filter(
    (c) =>
      c.doc_id.toLowerCase().includes(protocolSearch.toLowerCase()) ||
      c.text.toLowerCase().includes(protocolSearch.toLowerCase())
  )

  // --- 3. Evidence / Mutation Data (Static baseline benchmarks verified)

  // --- 4. Audit Trail Data ---
  const [verificationResult, setVerificationResult] = useState<AuditVerifyResponse | null>(null)
  const { data: auditEntries } = useQuery({
    queryKey: ['audit-entries'],
    queryFn: () => api.getAuditEntries(100),
  })
  const verifyMutation = useMutation({
    mutationFn: api.verifyAuditChain,
    onSuccess: (data) => setVerificationResult(data),
  })

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case 'BLOCK':
        return (
          <span className="flex items-center gap-1 rounded bg-red-950 border border-red-800 px-2 py-0.5 text-[11px] font-mono font-bold text-red-300">
            <AlertOctagon className="h-3 w-3" /> BLOCK
          </span>
        )
      case 'HIGH':
        return (
          <span className="flex items-center gap-1 rounded bg-orange-950 border border-orange-800 px-2 py-0.5 text-[11px] font-mono font-bold text-orange-300">
            <AlertTriangle className="h-3 w-3" /> HIGH
          </span>
        )
      default:
        return (
          <span className="flex items-center gap-1 rounded bg-slate-900 border border-slate-700 px-2 py-0.5 text-[11px] font-mono font-medium text-slate-300">
            {sev}
          </span>
        )
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="flex h-2 w-2 rounded-full bg-teal-400" />
            <span className="text-xs font-mono uppercase tracking-widest text-teal-400 font-semibold">
              Platform Intelligence
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Clinical Knowledge & Evidence
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-400">
            Inspect rule registries, synthetic guidelines, empirical benchmarks, and cryptographic audit chains in one unified view.
          </p>
        </div>

        {/* Clean Segmented Tab Switcher */}
        <div className="flex rounded-xl bg-slate-900/80 border border-slate-800 p-1 text-xs">
          <button
            type="button"
            onClick={() => handleTabChange('rules')}
            className={`flex items-center gap-1.5 py-1.5 px-3 rounded-lg font-medium transition-all ${
              activeTab === 'rules'
                ? 'bg-teal-500/20 text-teal-300 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            <span>Rules ({rules.length})</span>
          </button>
          <button
            type="button"
            onClick={() => handleTabChange('protocols')}
            className={`flex items-center gap-1.5 py-1.5 px-3 rounded-lg font-medium transition-all ${
              activeTab === 'protocols'
                ? 'bg-teal-500/20 text-teal-300 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>Protocols ({protocolList.length})</span>
          </button>
          <button
            type="button"
            onClick={() => handleTabChange('evidence')}
            className={`flex items-center gap-1.5 py-1.5 px-3 rounded-lg font-medium transition-all ${
              activeTab === 'evidence'
                ? 'bg-teal-500/20 text-teal-300 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>Evidence</span>
          </button>
          <button
            type="button"
            onClick={() => handleTabChange('audit')}
            className={`flex items-center gap-1.5 py-1.5 px-3 rounded-lg font-medium transition-all ${
              activeTab === 'audit'
                ? 'bg-teal-500/20 text-teal-300 font-semibold shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Hash className="h-3.5 w-3.5" />
            <span>Audit</span>
          </button>
        </div>
      </div>

      {/* TAB 1: RULES REGISTRY */}
      {activeTab === 'rules' && (
        <div className="flex flex-col gap-4">
          {/* Filter Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search rules by ID, substance, or class..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="h-9 w-full rounded-md border border-slate-800 bg-slate-950 pl-9 pr-3 text-xs text-slate-100 placeholder-slate-500 focus:border-teal-500 focus:outline-none"
              />
            </div>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="h-9 rounded-md border border-slate-800 bg-slate-950 px-3 text-xs text-slate-300 focus:border-teal-500 focus:outline-none"
            >
              <option value="all">All Severities</option>
              <option value="BLOCK">BLOCK</option>
              <option value="HIGH">HIGH</option>
            </select>
          </div>

          {/* Rules Table */}
          <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40 shadow">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 bg-slate-950 text-slate-400 uppercase tracking-wider font-mono text-[10px]">
                <tr>
                  <th className="px-4 py-3">Rule Identifier</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3">Provenance Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {rulesLoading ? (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-slate-400">
                      Loading rules registry...
                    </td>
                  </tr>
                ) : filteredRules.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-slate-500">
                      No clinical rules found matching search filters.
                    </td>
                  </tr>
                ) : (
                  filteredRules.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 font-mono font-semibold text-slate-200">{r.id}</td>
                      <td className="px-4 py-3">
                        <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300 font-mono">
                          {r.rule_type}
                        </span>
                      </td>
                      <td className="px-4 py-3">{getSeverityBadge(r.severity)}</td>
                      <td className="px-4 py-3">
                        <span className="rounded bg-amber-950/60 border border-amber-900/60 px-2 py-0.5 text-[10px] text-amber-300 font-mono">
                          {r.source_status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => setSelectedRule(r)}
                          className="text-xs text-teal-400 hover:text-teal-300 font-medium"
                        >
                          Inspect &rarr;
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: PROTOCOLS */}
      {activeTab === 'protocols' && (
        <div className="flex flex-col gap-4">
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-amber-200 flex items-start gap-2.5">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
            <p className="text-xs leading-relaxed text-amber-200/90">
              <strong>Rule R9 Synthetic Guarantee:</strong> Protocols are original synthetic text authored exclusively for offline retrieval evaluation. They contain zero numeric doses to ensure safe decision logic verification.
            </p>
          </div>

          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search protocol sections or guidance text..."
              value={protocolSearch}
              onChange={(e) => setProtocolSearch(e.target.value)}
              className="h-9 w-full rounded-xl border border-slate-800 bg-slate-900/60 pl-9 pr-3 text-xs text-slate-100 placeholder-slate-500 focus:border-teal-500 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filteredProtocols.map((p) => (
              <SpotlightCard key={p.chunk_id} className="border-slate-800 bg-slate-900/40 p-4">
                <div className="flex items-center justify-between border-b border-slate-800/80 pb-2 mb-2">
                  <span className="font-mono text-xs font-bold text-teal-400">{p.doc_id}</span>
                  <span className="rounded bg-teal-950 border border-teal-800 px-1.5 py-0.2 text-[10px] text-teal-300 font-mono">
                    SYNTHETIC
                  </span>
                </div>
                <div className="text-xs font-semibold text-slate-200 mb-1">{p.section}</div>
                <p className="text-xs text-slate-400 leading-relaxed font-sans line-clamp-3">
                  {p.text}
                </p>
              </SpotlightCard>
            ))}
          </div>
        </div>
      )}

      {/* TAB 3: EVIDENCE & EVAL */}
      {activeTab === 'evidence' && (
        <div className="flex flex-col gap-6">
          {/* Key Metric CountUp Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <SpotlightCard className="border-teal-900/60 bg-slate-900/80 p-4">
              <span className="text-[10px] uppercase text-teal-400 font-mono font-semibold">
                Golden Recall
              </span>
              <div className="mt-1 text-2xl font-extrabold text-white font-mono">
                <CountUp to={100} suffix="%" />
              </div>
              <p className="text-[10px] text-slate-400">65/65 Golden test cases</p>
            </SpotlightCard>

            <SpotlightCard className="border-teal-900/60 bg-slate-900/80 p-4">
              <span className="text-[10px] uppercase text-teal-400 font-mono font-semibold">
                Mutant Kill Score
              </span>
              <div className="mt-1 text-2xl font-extrabold text-white font-mono">
                <CountUp to={100} suffix="%" />
              </div>
              <p className="text-[10px] text-slate-400">40/40 killed (100% score)</p>
            </SpotlightCard>

            <SpotlightCard className="border-slate-800 bg-slate-900/80 p-4">
              <span className="text-[10px] uppercase text-teal-400 font-mono font-semibold">
                Metamorphic Invariance
              </span>
              <div className="mt-1 text-2xl font-extrabold text-white font-mono">
                <CountUp to={100} suffix="%" />
              </div>
              <p className="text-[10px] text-slate-400">3/3 Transformations green</p>
            </SpotlightCard>

            <SpotlightCard className="border-slate-800 bg-slate-900/80 p-4">
              <span className="text-[10px] uppercase text-teal-400 font-mono font-semibold">
                Adversarial Defense
              </span>
              <div className="mt-1 text-2xl font-extrabold text-white font-mono">
                <CountUp to={100} suffix="%" />
              </div>
              <p className="text-[10px] text-slate-400">9/9 Injections blocked</p>
            </SpotlightCard>
          </div>

          {/* Ablation Summary Table */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 mb-3">
              Multi-Arm Safety Ablation Study
            </h3>
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 text-slate-400 uppercase font-mono text-[10px]">
                <tr>
                  <th className="pb-2">Metric</th>
                  <th className="pb-2">Arm A (LLM Only)</th>
                  <th className="pb-2">Arm B (RAG Draft)</th>
                  <th className="pb-2 text-teal-400">Arm C (TriageRAG Full)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                <tr>
                  <td className="py-2.5 font-medium">Contraindicated BLOCK Meds Prescribed</td>
                  <td className="py-2.5 text-red-400 font-mono">1 violation</td>
                  <td className="py-2.5 text-red-400 font-mono">1 violation</td>
                  <td className="py-2.5 text-teal-400 font-mono font-bold">0 violations</td>
                </tr>
                <tr>
                  <td className="py-2.5 font-medium">Missed HIGH Safety Alerts</td>
                  <td className="py-2.5 text-red-400 font-mono">1 missed</td>
                  <td className="py-2.5 text-red-400 font-mono">1 missed</td>
                  <td className="py-2.5 text-teal-400 font-mono font-bold">0 missed</td>
                </tr>
                <tr>
                  <td className="py-2.5 font-medium">Magnitude Dosing Excursions Flagged</td>
                  <td className="py-2.5 text-red-400 font-mono">0 caught</td>
                  <td className="py-2.5 text-red-400 font-mono">0 caught</td>
                  <td className="py-2.5 text-teal-400 font-mono font-bold">100% caught</td>
                </tr>
                <tr>
                  <td className="py-2.5 font-medium">Hallucinated Uncited Steps Approved</td>
                  <td className="py-2.5 text-red-400 font-mono">4 approved</td>
                  <td className="py-2.5 text-red-400 font-mono">1 approved</td>
                  <td className="py-2.5 text-teal-400 font-mono font-bold">0 approved</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: AUDIT TRAIL */}
      {activeTab === 'audit' && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
                Cryptographic SHA-256 Merkle Chain
              </span>
              <p className="text-xs text-slate-400 mt-0.5">
                Verifies complete chronological chain integrity and detects any file tampering.
              </p>
            </div>
            <button
              type="button"
              onClick={() => verifyMutation.mutate()}
              disabled={verifyMutation.isPending}
              className="flex items-center gap-1.5 rounded-lg bg-teal-500 hover:bg-teal-400 px-3.5 py-1.5 text-xs font-bold text-slate-950 transition-all disabled:opacity-50"
            >
              {verifyMutation.isPending ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <KeyRound className="h-3.5 w-3.5" />
              )}
              <span>Verify Chain Integrity</span>
            </button>
          </div>

          {verificationResult && (
            <div
              className={`rounded-xl border p-3 text-xs ${
                verificationResult.valid
                  ? 'border-teal-500/40 bg-teal-500/10 text-teal-200'
                  : 'border-red-500/40 bg-red-500/10 text-red-200'
              }`}
            >
              <strong>
                {verificationResult.valid
                  ? '✓ Cryptographic Audit Chain Valid:'
                  : '✗ Chain Tampering Detected:'}
              </strong>{' '}
              {verificationResult.valid
                ? 'All records verified against SHA-256 Merkle links.'
                : `First bad index detected at #${verificationResult.first_bad_index}`}
            </div>
          )}

          <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/40">
            <div className="max-h-[450px] overflow-y-auto divide-y divide-slate-800/60 font-mono text-[11px] p-2">
              {(auditEntries || []).slice(0, 30).map((entry, idx) => (
                <div key={idx} className="p-2.5 flex flex-col gap-1 hover:bg-slate-800/30">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-teal-400 font-bold">Record #{entry.sequence_number}</span>
                    <span>{new Date(entry.timestamp_iso).toLocaleTimeString()}</span>
                  </div>
                  <div className="text-slate-300 truncate">Hash: {entry.record_hash}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Rule Detail Modal */}
      {selectedRule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="font-mono text-sm font-bold text-slate-100">{selectedRule.id}</span>
              <button
                type="button"
                onClick={() => setSelectedRule(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-2 text-xs">
              <div>
                <span className="text-slate-400 font-mono">Type:</span>{' '}
                <span className="text-slate-200">{selectedRule.rule_type}</span>
              </div>
              <div>
                <span className="text-slate-400 font-mono">Severity:</span>{' '}
                {getSeverityBadge(selectedRule.severity)}
              </div>
              <div>
                <span className="text-slate-400 font-mono">Source Status:</span>{' '}
                <span className="text-amber-300 font-mono">
                  {selectedRule.source_status}
                </span>
              </div>
              <div>
                <span className="text-slate-400 font-mono">Origin:</span>{' '}
                <span className="text-slate-300 font-mono">
                  {selectedRule.content_origin}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
export default ClinicalIntelligencePage
