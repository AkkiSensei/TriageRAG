import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Sparkles, ArrowRight } from 'lucide-react'
import { useTriage } from '@/context/TriageContext'

export const TryDemoButton: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { loadDemoPatient, isDemoActive } = useTriage()
  const isIntake = location.pathname === '/intake'

  const handleTryDemo = () => {
    loadDemoPatient()
    navigate('/intake')
  }

  return (
    <button
      type="button"
      onClick={handleTryDemo}
      aria-label="Try Demo - Synthetic Patient Scenario"
      className={`fixed z-40 left-4 ${
        isIntake ? 'bottom-28 sm:bottom-6' : 'bottom-4 sm:bottom-6'
      } sm:left-6 print:hidden pointer-events-auto group flex items-center gap-2.5 rounded-full bg-gradient-to-r from-teal-700 via-teal-800 to-teal-900 hover:from-teal-600 hover:to-teal-800 dark:from-teal-600 dark:via-teal-700 dark:to-teal-800 dark:hover:from-teal-500 dark:hover:to-teal-700 text-white pl-3.5 pr-4 py-2.5 shadow-soft-lg hover:shadow-glow transition-all duration-200 border border-teal-400/30 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2 dark:focus:ring-offset-slate-900 active:scale-95`}
      style={{
        left: 'max(1rem, env(safe-area-inset-left, 1rem))',
      }}
    >
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/20 text-white backdrop-blur-xs group-hover:bg-white/30 transition-colors">
        <Sparkles className="h-4 w-4 text-amber-200 animate-pulse" />
      </span>
      <div className="flex flex-col items-start text-left">
        <div className="flex items-center gap-1.5 leading-none">
          <span className="text-xs font-bold tracking-tight">Try Demo</span>
          <span className="rounded-full bg-teal-950/70 border border-teal-300/40 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-teal-200">
            Synthetic
          </span>
        </div>
        <span className="text-[10px] text-teal-100/90 leading-tight">
          {isDemoActive ? 'Demo loaded · Review' : 'Contraindication test'}
        </span>
      </div>
      <ArrowRight className="h-3.5 w-3.5 text-teal-200 transition-transform group-hover:translate-x-0.5" />
    </button>
  )
}

export default TryDemoButton
