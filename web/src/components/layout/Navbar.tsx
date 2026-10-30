import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Activity,
  Stethoscope,
  FileSpreadsheet,
  BookOpen,
  FileCode2,
  Menu,
  X,
  Sparkles,
  Sun,
  Moon,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useTheme } from '@/context/ThemeContext'

interface NavItem {
  to: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/intake', label: 'Intake Station', icon: Stethoscope },
  { to: '/report', label: 'Clinical Report', icon: FileSpreadsheet },
  { to: '/rules', label: 'Ruleset', icon: BookOpen },
  { to: '/protocols', label: 'Protocols', icon: FileCode2 },
]

export const Navbar: React.FC = () => {
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { isDark, toggleTheme } = useTheme()

  const { isSuccess } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30000,
  })

  return (
    <header className="sticky top-0 z-40 w-full px-3 sm:px-6 lg:px-8 py-2.5">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 rounded-2xl bg-white/90 dark:bg-[#132226]/90 backdrop-blur-md border border-[#d9e8e6] dark:border-[#1e3840] shadow-soft text-slate-800 dark:text-slate-100 transition-all">
        {/* Brand */}
        <div className="flex items-center gap-4 lg:gap-6">
          <Link
            to="/intake"
            className="group flex items-center gap-3 transition-transform hover:scale-[1.01]"
            title="TriageRAG Emergency Decision Support"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-[#0f766e] to-[#115e59] dark:from-teal-500 dark:to-teal-700 text-white shadow-[0_4px_12px_rgba(15,118,110,0.25)] ring-2 ring-[#99f6e4]/40 dark:ring-teal-400/30">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="text-base font-extrabold tracking-tight text-slate-900 dark:text-white leading-tight">
                  Triage<span className="text-teal-700 dark:text-teal-400">RAG</span>
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider bg-teal-50 dark:bg-teal-950/80 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800 px-2 py-0.5 rounded-full">
                  Console
                </span>
              </div>
              <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium leading-tight">
                Deterministic Decision Support
              </span>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <nav className="hidden lg:flex items-center gap-1 pl-4 border-l border-slate-200 dark:border-slate-700/60 text-xs font-medium">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname.startsWith(item.to)
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-xl transition-all ${
                    isActive
                      ? 'bg-teal-700 dark:bg-teal-600 text-white font-semibold shadow-sm'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100/70 dark:hover:bg-slate-800/60'
                  }`}
                >
                  <Icon
                    className={`h-3.5 w-3.5 ${
                      isActive ? 'text-teal-200' : 'text-slate-400 dark:text-slate-500'
                    }`}
                  />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span
                      className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded-full ${
                        isActive
                          ? 'bg-teal-800 dark:bg-teal-700 text-teal-100'
                          : 'bg-coral-50 dark:bg-coral-950/60 text-coral-600 dark:text-coral-400 border border-coral-200 dark:border-coral-800/60'
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

        {/* Right: Disclaimer Badge, Theme Toggle, API Status, and Mobile Toggle */}
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="hidden md:flex items-center gap-1.5 rounded-full bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 px-3 py-1 text-[11px] font-medium text-amber-800 dark:text-amber-300 shadow-soft-sm">
            <Sparkles className="h-3 w-3 text-amber-600 dark:text-amber-400 shrink-0" />
            <span>Research Prototype • Synthetic Data</span>
          </div>

          {/* Theme Toggle Button */}
          <button
            type="button"
            onClick={toggleTheme}
            className="flex items-center justify-center h-9 w-9 rounded-xl border border-slate-200 dark:border-[#223d45] bg-slate-50 dark:bg-[#182b30] text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-[#203940] transition-colors shadow-soft-sm"
            aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
            title={isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme'}
          >
            {isDark ? (
              <Sun className="h-4 w-4 text-amber-400 animate-in spin-in-90 duration-300" />
            ) : (
              <Moon className="h-4 w-4 text-slate-600 animate-in spin-in-90 duration-300" />
            )}
          </button>

          {/* API Health Pill */}
          <div
            className="flex items-center gap-1.5 rounded-full bg-slate-50 dark:bg-[#182b30] border border-slate-200 dark:border-[#223d45] px-2.5 sm:px-3 py-1 text-[11px] font-mono text-slate-700 dark:text-slate-200 shadow-soft-sm"
            title={isSuccess ? 'Deterministic API connected' : 'Connecting to API...'}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                isSuccess
                  ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)] animate-pulse'
                  : 'bg-amber-400'
              }`}
            />
            <span className="font-semibold hidden sm:inline">{isSuccess ? 'ONLINE' : 'CONNECTING'}</span>
          </div>

          {/* Mobile menu toggle */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="flex lg:hidden items-center justify-center h-9 w-9 rounded-xl border border-slate-200 dark:border-[#223d45] bg-slate-50 dark:bg-[#182b30] text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-[#203940]"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden mt-2 mx-auto max-w-7xl rounded-2xl bg-white/95 dark:bg-[#132226]/95 backdrop-blur-md border border-[#d9e8e6] dark:border-[#1e3840] p-3 shadow-soft-lg transition-all">
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
                      ? 'bg-teal-700 dark:bg-teal-600 text-white font-semibold'
                      : 'text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon
                      className={`h-4 w-4 ${
                        isActive ? 'text-teal-200' : 'text-slate-400 dark:text-slate-500'
                      }`}
                    />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                        isActive
                          ? 'bg-teal-800 dark:bg-teal-700 text-teal-100'
                          : 'bg-coral-50 dark:bg-coral-950/60 text-coral-600 dark:text-coral-400'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              )
            })}
          </div>
          <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-slate-800 text-[11px] text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 rounded-xl p-2.5 text-center font-medium">
            Synthetic data only. Not a medical device. Not for clinical use.
          </div>
        </div>
      )}
    </header>
  )
}

export default Navbar
