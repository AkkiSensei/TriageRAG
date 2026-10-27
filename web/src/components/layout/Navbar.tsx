import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Activity, ChevronRight, Stethoscope, FileSpreadsheet } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export const Navbar: React.FC = () => {
  const location = useLocation()
  const isReport = location.pathname.startsWith('/report')

  const { isSuccess } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30000,
  })

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Left: Hospital-grade Brand & Workflow Steps */}
        <div className="flex items-center gap-6">
          <Link
            to="/intake"
            className="flex items-center gap-2.5 transition-opacity hover:opacity-90"
            title="TriageRAG Clinical Decision Support"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-400">
              <Activity className="h-4.5 w-4.5" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold tracking-tight text-white flex items-center gap-1.5">
                TriageRAG <span className="text-xs font-normal text-teal-400">Station</span>
              </span>
              <span className="text-[10px] text-slate-400 font-mono">
                Emergency Decision Support
              </span>
            </div>
          </Link>

          {/* Workflow Step Indicators */}
          <nav className="hidden sm:flex items-center gap-1.5 pl-4 border-l border-slate-800 text-xs font-medium">
            <Link
              to="/intake"
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-colors ${
                !isReport
                  ? 'bg-slate-800 text-teal-400 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Stethoscope className="h-3.5 w-3.5" />
              <span>1. Patient Intake</span>
            </Link>

            <ChevronRight className="h-3.5 w-3.5 text-slate-600" />

            <Link
              to="/report"
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-colors ${
                isReport
                  ? 'bg-slate-800 text-teal-400 font-semibold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileSpreadsheet className="h-3.5 w-3.5" />
              <span>2. Clinical Report</span>
            </Link>
          </nav>
        </div>

        {/* Right: Disclaimer and API Health */}
        <div className="flex items-center gap-3">
          <span className="hidden md:inline rounded bg-slate-900 border border-slate-800 px-2 py-0.5 text-[10px] font-mono text-amber-400">
            Research Prototype • Synthetic Data
          </span>

          <div
            className="flex items-center gap-1.5 rounded-full bg-slate-900 border border-slate-800 px-2.5 py-1 text-[11px] font-mono text-slate-300"
            title={isSuccess ? 'Backend API Connected' : 'Connecting to API...'}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                isSuccess ? 'bg-teal-400 shadow-[0_0_6px_rgba(20,184,166,0.6)]' : 'bg-amber-400'
              }`}
            />
            <span className="hidden sm:inline">{isSuccess ? 'API Online' : 'Connecting'}</span>
          </div>
        </div>
      </div>
    </header>
  )
}
export default Navbar
