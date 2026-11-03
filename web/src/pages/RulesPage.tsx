import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, type RuleSummaryDto } from '@/lib/api'
import {
  ShieldCheck,
  Search,
  AlertOctagon,
  AlertTriangle,
  Info,
  Loader2,
  FileQuestion,
  CheckCircle,
} from 'lucide-react'

export const RulesPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeFilter, setActiveFilter] = useState<string>('ALL')

  const { data: summary } = useQuery({
    queryKey: ['registry-summary'],
    queryFn: api.getRegistrySummary,
  })

  const { data: rules, isLoading: isLoadingRules } = useQuery({
    queryKey: ['rules'],
    queryFn: api.getRules,
  })

  // Review status helper: "Approved", "Needs review", "Draft"
  // Note: Candidate rules can NEVER appear as approved
  const getReviewStatus = (rule: RuleSummaryDto): 'Approved' | 'Needs review' | 'Draft' => {
    const isCandidate =
      rule.content_origin?.includes('CANDIDATE') ||
      rule.status?.includes('CANDIDATE') ||
      rule.id.toLowerCase().includes('candidate')

    if (isCandidate) return 'Draft'
    if (rule.verified === true) return 'Approved'
    if (rule.source_status === 'RETRIEVED_UNREVIEWED' || rule.status === 'NEEDS_SOURCE') {
      return 'Needs review'
    }
    return 'Draft'
  }

  const getReviewStatusBadge = (rule: RuleSummaryDto) => {
    const status = getReviewStatus(rule)
    switch (status) {
      case 'Approved':
        return (
          <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 dark:bg-emerald-950/70 text-emerald-900 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700">
            Approved
          </span>
        )
      case 'Needs review':
        return (
          <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 dark:bg-amber-950/70 text-amber-900 dark:text-amber-300 border border-amber-300 dark:border-amber-700">
            Needs review
          </span>
        )
      case 'Draft':
      default:
        return (
          <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
            Draft
          </span>
        )
    }
  }

  // Friendly human readable title for rules
  const getFriendlyRuleTitle = (rule: RuleSummaryDto) => {
    const id = rule.id.toUpperCase()
    if (id.includes('SILDENAFIL') || id.includes('NITRO')) {
      return 'Do Not Mix Silagra / Sildenafil with Nitroglycerin'
    }
    if (id.includes('TADALAFIL')) {
      return 'Do Not Mix Tadalafil (Cialis) with Nitroglycerin'
    }
    if (id.includes('PENICILLIN') || id.includes('AMOXICILLIN')) {
      return 'Penicillin & Amoxicillin Allergy Safety Rule'
    }
    if (id.includes('CEFTRIAXONE') || id.includes('CEPHALOSPORIN')) {
      return 'Ceftriaxone & Antibiotic Cross-Allergy Check'
    }
    if (id.includes('HYPOTENSION') || id.includes('BP')) {
      return 'Low Blood Pressure Safety Limit'
    }
    if (id.includes('BRADYCARDIA') || id.includes('HR')) {
      return 'Slow Heart Rate (Bradycardia) Safety Limit'
    }
    if (id.includes('TACHYCARDIA')) {
      return 'Fast Heart Rate Safety Check'
    }
    if (id.includes('RENAL') || id.includes('KIDNEY')) {
      return 'Kidney Health Dose Adjustment Rule'
    }
    if (id.includes('HEPATIC') || id.includes('LIVER')) {
      return 'Liver Health Safety Rule'
    }
    if (id.includes('AGE') || id.includes('PAED') || id.includes('CHILD')) {
      return 'Child / Pediatric Age Safety Rule'
    }
    if (id.includes('PREGNAN')) {
      return 'Pregnancy Medication Safety Rule'
    }
    // Fallback: format id into clean title
    return rule.id
      .replace(/_/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase())
  }

  const filteredRules = (rules || []).filter((rule) => {
    const status = getReviewStatus(rule)
    let matchesFilter = true
    if (activeFilter === 'BLOCK') matchesFilter = rule.severity.toUpperCase() === 'BLOCK'
    else if (activeFilter === 'HIGH') matchesFilter = rule.severity.toUpperCase() === 'HIGH'
    else if (activeFilter === 'MODERATE') matchesFilter = rule.severity.toUpperCase() === 'MODERATE'
    else if (activeFilter === 'APPROVED') matchesFilter = status === 'Approved'
    else if (activeFilter === 'NEEDS_REVIEW') matchesFilter = status === 'Needs review'
    else if (activeFilter === 'DRAFT') matchesFilter = status === 'Draft'

    const friendlyTitle = getFriendlyRuleTitle(rule)
    const matchesSearch =
      searchQuery === '' ||
      friendlyTitle.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.consequence?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.action?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rule.rule_type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      status.toLowerCase().includes(searchQuery.toLowerCase())

    return matchesFilter && matchesSearch
  })

  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case 'BLOCK':
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-100 dark:bg-rose-950/70 text-rose-900 dark:text-rose-200 border border-rose-300 dark:border-rose-700">
            <AlertOctagon className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" />
            <span>DANGER / STOP</span>
          </span>
        )
      case 'HIGH':
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 dark:bg-amber-950/70 text-amber-950 dark:text-amber-200 border border-amber-300 dark:border-amber-700">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
            <span>DOCTOR REVIEW</span>
          </span>
        )
      case 'MODERATE':
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 dark:bg-amber-950/50 text-amber-900 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
            <span>CAUTION</span>
          </span>
        )
      case 'INFO':
      default:
        return (
          <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-sky-50 dark:bg-sky-950/50 text-sky-900 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
            <Info className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400" />
            <span>NOTE</span>
          </span>
        )
    }
  }

  // Format field names into friendly terms
  const formatFields = (fields?: string[]) => {
    if (!fields || fields.length === 0) return 'Basic patient vitals'
    return fields
      .map((f) => {
        if (f.includes('sbp') || f.includes('systolic')) return 'Upper Blood Pressure'
        if (f.includes('dbp') || f.includes('diastolic')) return 'Lower Blood Pressure'
        if (f.includes('hr') || f.includes('heart_rate')) return 'Heart Rate'
        if (f.includes('spo2')) return 'Oxygen Level (SpO2)'
        if (f.includes('medication')) return 'Current Regular Medicines'
        if (f.includes('allergy')) return 'Known Medicine Allergies'
        if (f.includes('age')) return 'Patient Age'
        if (f.includes('pregnancy')) return 'Pregnancy Status'
        return f.replace(/_/g, ' ')
      })
      .join(', ')
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-2 rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 sm:p-6 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <span className="text-xs font-bold uppercase tracking-wider text-teal-700 dark:text-teal-400">
            Hospital Patient Safety
          </span>
        </div>
        <h1 className="text-2xl font-black tracking-tight text-slate-900 dark:text-white sm:text-3xl">
          Safety Rules
        </h1>
        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-2xl leading-relaxed">
          These automatic rules check medicine combinations, safe doses, and allergies to protect patients from harmful interactions.
        </p>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="mb-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 block">Total Safety Rules</span>
            <span className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white mt-1 block">
              {summary.rules_count}
            </span>
          </div>
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 block">Formulary Medicines</span>
            <span className="text-xl sm:text-2xl font-extrabold text-teal-600 dark:text-teal-400 mt-1 block">
              {summary.formulary_drugs_count}
            </span>
          </div>
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 block">Stop Rules (Danger)</span>
            <span className="text-xl sm:text-2xl font-extrabold text-rose-600 dark:text-rose-400 mt-1 block">
              {summary.rules_by_severity?.BLOCK || 0}
            </span>
          </div>
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-sm">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 block">Rule Status</span>
            <span className="text-xs font-bold text-teal-700 dark:text-teal-400 mt-2 block flex items-center gap-1">
              <CheckCircle className="h-3.5 w-3.5" />
              Active in Software
            </span>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="mb-6 flex flex-col sm:flex-row items-center justify-between gap-3 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-3.5 shadow-sm">
        <div className="relative w-full sm:w-80 flex items-center">
          <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search rules (e.g. Silagra, Penicillin, Blood Pressure)..."
            className="h-10 w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 pl-10 pr-4 text-xs sm:text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
        </div>

        <div className="flex items-center gap-1.5 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
          {[
            { id: 'ALL', label: 'All Rules' },
            { id: 'BLOCK', label: 'Stop Rules' },
            { id: 'HIGH', label: 'Doctor Review' },
            { id: 'MODERATE', label: 'Caution' },
            { id: 'APPROVED', label: 'Approved' },
            { id: 'NEEDS_REVIEW', label: 'Needs Review' },
            { id: 'DRAFT', label: 'Draft' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveFilter(item.id)}
              className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all shrink-0 cursor-pointer ${
                activeFilter === item.id
                  ? 'bg-teal-600 text-white shadow-sm'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {isLoadingRules && (
        <div className="flex flex-col items-center justify-center p-12 text-slate-500">
          <Loader2 className="h-8 w-8 animate-spin text-teal-600 mb-2" />
          <span className="text-xs font-medium">Loading safety rules...</span>
        </div>
      )}

      {/* Rules list */}
      {!isLoadingRules && (
        <div className="flex flex-col gap-4">
          {filteredRules.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-10 text-center shadow-sm">
              <FileQuestion className="h-8 w-8 text-slate-400 mb-2" />
              <span className="text-sm font-bold text-slate-700 dark:text-slate-200">No matching safety rules found</span>
              <p className="text-xs text-slate-400 mt-1">Try searching with a different medicine name or symptom.</p>
            </div>
          ) : (
            filteredRules.map((rule: RuleSummaryDto) => (
              <div
                key={rule.id}
                className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 sm:p-6 shadow-sm hover:shadow-md transition-all"
              >
                {/* Rule Title and Badges */}
                <div className="flex items-start justify-between gap-3 flex-wrap mb-4 pb-3 border-b border-slate-100 dark:border-slate-800">
                  <div>
                    <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white">
                      {getFriendlyRuleTitle(rule)}
                    </h3>
                    <span className="text-[11px] text-slate-400 dark:text-slate-500 font-mono mt-0.5 block">
                      Rule Code: {rule.id}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {getSeverityBadge(rule.severity)}
                    {getReviewStatusBadge(rule)}
                  </div>
                </div>

                {/* 3 User-Friendly Staff Questions */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* 1. What is this rule? */}
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 p-3.5 border border-slate-100 dark:border-slate-800">
                    <span className="text-xs font-bold text-slate-900 dark:text-white block mb-1">
                      1. What is this rule?
                    </span>
                    <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                      {rule.consequence || 'Protects the patient from harmful medicine interactions.'}
                    </p>
                  </div>

                  {/* 2. What should I check? */}
                  <div className="rounded-xl bg-slate-50 dark:bg-slate-800/60 p-3.5 border border-slate-100 dark:border-slate-800">
                    <span className="text-xs font-bold text-slate-900 dark:text-white block mb-1">
                      2. What should I check?
                    </span>
                    <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                      Check: {formatFields(rule.requires_fields)}.
                    </p>
                  </div>

                  {/* 3. When should I stop and ask for help? */}
                  <div className="rounded-xl bg-amber-50/70 dark:bg-amber-950/40 p-3.5 border border-amber-200 dark:border-amber-800/60">
                    <span className="text-xs font-bold text-amber-900 dark:text-amber-200 block mb-1">
                      3. When should I stop &amp; ask for help?
                    </span>
                    <p className="text-xs text-amber-950 dark:text-amber-200 leading-relaxed font-medium">
                      {rule.action || 'Stop immediately if this rule fires and call the doctor on duty.'}
                    </p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default RulesPage