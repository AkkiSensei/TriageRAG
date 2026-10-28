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
    <header className="sticky top-0 z-40 w-full px-3 sm:px-6 lg:px-8 py-2.5">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-3.5 sm:px-5 rounded-2xl bg-[#1A2421]/95 backdrop-blur-md border border-white/10 shadow-[0_8px_24px_rgba(0,0,0,0.12)] text-white">
        {/* Left: Hospital-grade Brand & Workflow Steps */}
        <div className="flex items-center gap-4 sm:gap-6">
          <Link
            to="/intake"
            className="flex items-center gap-2.5 transition-opacity hover:opacity-90"
            title="TriageRAG Clinical Decision Support"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#2D6A4F] text-white shadow-sm">
              <Activity className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5 leading-tight">
                TriageRAG <span className="text-[10px] uppercase tracking-wider font-bold bg-[#2D6A4F] text-white px-1.5 py-0.5 rounded-full">Station</span>
              </span>
              <span className="text-[10px] text-[#A3B0A9] font-mono leading-tight">
                Clinical Decision Support
              </span>
            </div>
          </Link>

          {/* Workflow Step Indicators */}
          <nav className="hidden sm:flex items-center gap-1 pl-4 border-l border-white/15 text-xs font-medium">
            <Link
              to="/intake"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                !isReport
                  ? 'bg-[#2D6A4F] text-white font-semibold shadow-xs'
                  : 'text-[#A3B0A9] hover:text-white hover:bg-white/10'
              }`}
            >
              <Stethoscope className="h-3.5 w-3.5" />
              <span>1. Patient Intake</span>
            </Link>

            <ChevronRight className="h-3.5 w-3.5 text-white/40" />

            <Link
              to="/report"
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                isReport
                  ? 'bg-[#2D6A4F] text-white font-semibold shadow-xs'
                  : 'text-[#A3B0A9] hover:text-white hover:bg-white/10'
              }`}
            >
              <FileSpreadsheet className="h-3.5 w-3.5" />
              <span>2. Clinical Report</span>
            </Link>
          </nav>
        </div>

        {/* Right: Disclaimer and API Health */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          <span className="hidden md:inline rounded-full bg-amber-400/10 border border-amber-400/25 px-2.5 py-0.5 text-[10px] font-mono text-amber-300">
            Research Prototype • Synthetic Data
          </span>

          <div
            className="flex items-center gap-1.5 rounded-full bg-white/10 border border-white/15 px-2.5 py-1 text-[11px] font-mono text-white/90"
            title={isSuccess ? 'Backend API Connected' : 'Connecting to API...'}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                isSuccess ? 'bg-[#43A047] shadow-[0_0_6px_rgba(67,160,71,0.8)]' : 'bg-amber-400'
              }`}
            />
            <span className="hidden sm:inline font-bold">{isSuccess ? 'ONLINE' : 'CONNECTING'}</span>
          </div>
        </div>
      </div>
    </header>
  )
}

export default Navbar
