import React, { useRef, useState } from 'react'
import { useMotionOk } from '@/lib/motion'

interface SpotlightCardProps {
  children: React.ReactNode
  className?: string
  spotlightColor?: string
}

export const SpotlightCard: React.FC<SpotlightCardProps> = ({
  children,
  className = '',
  spotlightColor = 'rgba(20, 184, 166, 0.12)',
}) => {
  const divRef = useRef<HTMLDivElement | null>(null)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [opacity, setOpacity] = useState(0)
  const motionOk = useMotionOk()

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!motionOk || !divRef.current) return
    const rect = divRef.current.getBoundingClientRect()
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top })
  }

  const handleFocus = () => {
    if (motionOk) setOpacity(0.8)
  }

  const handleBlur = () => {
    if (motionOk) setOpacity(0)
  }

  const handleMouseEnter = () => {
    if (motionOk) setOpacity(0.8)
  }

  const handleMouseLeave = () => {
    if (motionOk) setOpacity(0)
  }

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`relative overflow-hidden rounded-xl border border-slate-800 bg-clinical-surface/80 p-6 backdrop-blur-sm transition-colors hover:border-slate-700 ${className}`}
    >
      {motionOk && (
        <div
          className="pointer-events-none absolute -inset-px transition-opacity duration-300"
          style={{
            opacity,
            background: `radial-gradient(600px circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 40%)`,
          }}
          aria-hidden="true"
        />
      )}
      <div className="relative z-10">{children}</div>
    </div>
  )
}
