import React, { createContext, useContext, useEffect, useState } from 'react'

interface MotionContextValue {
  motionOk: boolean
  reducedMotionPreferred: boolean
  userMotionPref: boolean | null
  setUserMotionPref: (pref: boolean | null) => void
}

const MotionContext = createContext<MotionContextValue>({
  motionOk: true,
  reducedMotionPreferred: false,
  userMotionPref: null,
  setUserMotionPref: () => {},
})

export const MotionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [reducedMotionPreferred, setReducedMotionPreferred] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })

  const [userMotionPref, setUserMotionPref] = useState<boolean | null>(() => {
    if (typeof window === 'undefined') return null
    const saved = localStorage.getItem('triagerag-motion-pref')
    return saved !== null ? saved === 'true' : null
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e: MediaQueryListEvent) => {
      setReducedMotionPreferred(e.matches)
    }
    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [])

  const handleSetUserPref = (pref: boolean | null) => {
    setUserMotionPref(pref)
    if (typeof window !== 'undefined') {
      if (pref === null) {
        localStorage.removeItem('triagerag-motion-pref')
      } else {
        localStorage.setItem('triagerag-motion-pref', String(pref))
      }
    }
  }

  // Motion is allowed ONLY IF:
  // 1. User didn't explicitly disable it
  // 2. AND System prefers-reduced-motion is false (unless user explicitly forced it true)
  const motionOk = userMotionPref !== null ? userMotionPref : !reducedMotionPreferred

  return (
    <MotionContext.Provider
      value={{
        motionOk,
        reducedMotionPreferred,
        userMotionPref,
        setUserMotionPref: handleSetUserPref,
      }}
    >
      {children}
    </MotionContext.Provider>
  )
}

export function useMotionOk(): boolean {
  return useContext(MotionContext).motionOk
}

export function useMotionSettings() {
  return useContext(MotionContext)
}

interface MotionGuardProps {
  children: React.ReactNode
  fallback?: React.ReactNode
  className?: string
}

/**
 * `<Motion>` Guard: renders animated children ONLY if motion is permitted (respects prefers-reduced-motion
 * and user toggle). If motion is not permitted, renders static fallback or plain un-animated container.
 *
 * NOTE: S1 Safety Rule: Safety banner, alerts, blocked drugs, skipped checks, and the disclaimer
 * MUST NEVER be wrapped in <Motion> or any animation!
 */
export const Motion: React.FC<MotionGuardProps> = ({ children, fallback, className }) => {
  const motionOk = useMotionOk()

  if (!motionOk) {
    if (fallback !== undefined) {
      return <>{fallback}</>
    }
    return <div className={className}>{children}</div>
  }

  return <div className={className}>{children}</div>
}
