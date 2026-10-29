import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Activity,
  Stethoscope,
  FileSpreadsheet,
  Shield,
  BookOpen,
  FileCode2,
  LineChart,
  Hash,
  Menu,
  X,
  Sparkles,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

interface NavItem {
  to: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/intake', label: 'Intake Station', icon: Stethoscope },
  { to: '/report', label: 'Clinical Report', icon: FileSpreadsheet },
  { to: '/redteam', label: 'Red Team', icon: Shield, badge: 'R7' },
  { to: '/rules', label: 'Ruleset', icon: BookOpen },
  { to: '/protocols', label: 'Protocols', icon: FileCode2 },
  { to: '/evidence', label: 'Evidence', icon: LineChart },
  { to: '/audit', label: 'Audit Chain', icon: Hash },
]

export const Navbar: React.FC = () => {
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const { isSuccess } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30000,
  })

  return (
    <header className="sticky top-0 z-40 w-full px-3 sm:px-6 lg:px-8 py-2.5">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 rounded-2xl bg-white/90 backdrop-blur-md border border-[#d9e8e6] shadow-soft text-slate-800 transition-all">
        {/* Brand */}
        <div className="flex items-center gap-4 lg:gap-6">
          <Link
            to="/intake"
            className="group flex items-center gap-3 transition-transform hover:scale-[1.01]"
            title="TriageRAG Emergency Decision Support"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-[#0f766e] to-[#115e59] text-white shadow-[0_4px_12px_rgba(15,118,110,0.25)] ring-2 ring-[#99f6e4]/40">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="text-base font-extrabold tracking-tight text-slate-900 leading-tight">
                  Triage<span className="text-[#0f766e]">RAG</span>
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider bg-teal-50 text-[#0f766e] border border-teal-200 px-2 py-0.5 rounded-full">
                  Console
                </span>
              </div>
              <span className="text-[11px] text-slate-500 font-medium leading-tight">
                Deterministic Decision Support
              </span>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <nav className="hidden lg:flex items-center gap-1 pl-4 border-l border-slate-200 text-xs font-medium">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname.startsWith(item.to)
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-xl transition-all ${
                    isActive
                      ? 'bg-teal-700 text-white font-semibold shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70'
                  }`}
                >
                  <Icon className={`h-3.5 w-3.5 ${isActive ? 'text-teal-200' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span
                      className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded-full ${
                        isActive
                          ? 'bg-teal-800 text-teal-100'
                          : 'bg-coral-50 text-coral-600 border border-coral-200'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              )
            })}
          </nav>
        </div>

        {/* Right: Disclaimer Badge, API Status, and Mobile Toggle */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          <div className="hidden md:flex items-center gap-1.5 rounded-full bg-amber-50 border border-amber-200 px-3 py-1 text-[11px] font-medium text-amber-800 shadow-soft-sm">
            <Sparkles className="h-3 w-3 text-amber-600 shrink-0" />
            <span>Research Prototype • Synthetic Data</span>
          </div>

          <div
            className="flex items-center gap-1.5 rounded-full bg-slate-50 border border-slate-200 px-3 py-1 text-[11px] font-mono text-slate-700 shadow-soft-sm"
            title={isSuccess ? 'Deterministic API connected' : 'Connecting to API...'}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                isSuccess
                  ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)] animate-pulse'
                  : 'bg-amber-400'
              }`}
            />
            <span className="font-semibold">{isSuccess ? 'ONLINE' : 'CONNECTING'}</span>
          </div>

          {/* Mobile menu button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="flex lg:hidden items-center justify-center h-9 w-9 rounded-xl border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden mt-2 mx-auto max-w-7xl rounded-2xl bg-white/95 backdrop-blur-md border border-[#d9e8e6] p-3 shadow-soft-lg transition-all">
          <div className="flex flex-col gap-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname.startsWith(item.to)
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-teal-700 text-white font-semibold'
                      : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`h-4 w-4 ${isActive ? 'text-teal-200' : 'text-slate-400'}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                        isActive ? 'bg-teal-800 text-teal-100' : 'bg-coral-50 text-coral-600'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              )
            })}
          </div>
          <div className="mt-2 pt-2 border-t border-slate-100 text-[11px] text-amber-800 bg-amber-50 rounded-xl p-2 text-center font-medium">
            Synthetic data only. Not a medical device. Not for clinical use.
          </div>
        </div>
      )}
    </header>
  )
}

export default Navbar
