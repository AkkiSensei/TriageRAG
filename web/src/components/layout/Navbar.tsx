import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Activity, ShieldAlert, BookOpen, FileText, CheckCircle2, Info, Zap, ZapOff } from 'lucide-react'
import { useMotionSettings } from '@/lib/motion'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Magnet } from '@/components/reactbits'

export const Navbar: React.FC = () => {
  const location = useLocation()
  const { motionOk, userMotionPref, setUserMotionPref } = useMotionSettings()

  const { data: health, isSuccess } = useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    refetchInterval: 30000,
  })

  const navItems = [
    { label: 'Triage Console', path: '/', icon: Activity },
    { label: 'Ruleset', path: '/ruleset', icon: ShieldAlert },
    { label: 'Protocols', path: '/protocols', icon: BookOpen },
    { label: 'Evidence & Eval', path: '/evidence', icon: CheckCircle2 },
    { label: 'Audit Trail', path: '/audit', icon: FileText },
    { label: 'About', path: '/about', icon: Info },
  ]

  const toggleMotion = () => {
    if (userMotionPref === null) {
      setUserMotionPref(!motionOk)
    } else {
      setUserMotionPref(!userMotionPref)
    }
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-clinical-bg/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2.5 font-bold tracking-tight text-white transition-opacity hover:opacity-90">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-400 shadow-sm">
              <Activity className="h-5 w-5" />
            </div>
            <div className="flex flex-col">
              <span className="text-base font-semibold leading-tight text-slate-100 flex items-center gap-1.5">
                TriageRAG <span className="text-xs font-normal text-teal-400">Console</span>
              </span>
              <span className="text-[10px] tracking-wider uppercase text-amber-400 font-mono">Research Prototype</span>
            </div>
          </Link>
        </div>

        {/* Navigation links */}
        <nav className="hidden md:flex items-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                  isActive
                    ? 'bg-slate-800 text-teal-400 border border-slate-700 shadow-inner'
                    : 'text-slate-300 hover:bg-slate-800/60 hover:text-slate-100'
                }`}
              >
                <Icon className={`h-3.5 w-3.5 ${isActive ? 'text-teal-400' : 'text-slate-400'}`} />
                {item.label}
              </Link>
            )
          })}
        </nav>

        {/* Right action controls */}
        <div className="flex items-center gap-2">
          {/* Health indicator */}
          <div
            className="flex items-center gap-1.5 rounded-full bg-slate-900 border border-slate-800 px-2.5 py-1 text-[11px] font-mono text-slate-300"
            title={isSuccess ? `API Online: ${health?.unreviewed_rules_count ?? 0} unreviewed rules` : 'Connecting to API...'}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                isSuccess ? 'bg-teal-400 shadow-[0_0_8px_rgba(20,184,166,0.6)]' : 'bg-amber-400'
              }`}
            />
            <span className="hidden sm:inline">{isSuccess ? 'API Online' : 'Connecting'}</span>
          </div>

          {/* Motion preference toggle */}
          <Magnet distance={30} magnetStrength={0.2}>
            <button
              onClick={toggleMotion}
              className={`flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs font-mono transition-colors ${
                motionOk
                  ? 'border-teal-500/30 bg-teal-500/10 text-teal-300 hover:bg-teal-500/20'
                  : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-200'
              }`}
              title={motionOk ? 'Animations Enabled (Click to disable)' : 'Animations Disabled (Click to enable)'}
              aria-label="Toggle animations"
            >
              {motionOk ? <Zap className="h-3.5 w-3.5" /> : <ZapOff className="h-3.5 w-3.5" />}
              <span className="hidden sm:inline">{motionOk ? 'Motion On' : 'Reduced'}</span>
            </button>
          </Magnet>
        </div>
      </div>
    </header>
  )
}
