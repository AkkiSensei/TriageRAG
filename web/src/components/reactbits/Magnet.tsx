import React, { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { useMotionOk } from '@/lib/motion'

interface MagnetProps {
  children: React.ReactNode
  distance?: number
  magnetStrength?: number
  activeTransition?: string
  inactiveTransition?: string
  className?: string
}

export const Magnet: React.FC<MagnetProps> = ({
  children,
  distance = 60,
  magnetStrength = 0.3,
  className = '',
}) => {
  const ref = useRef<HTMLDivElement | null>(null)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const motionOk = useMotionOk()

  if (!motionOk) {
    return <div className={`inline-block ${className}`}>{children}</div>
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!ref.current) return
    const { left, top, width, height } = ref.current.getBoundingClientRect()
    const centerX = left + width / 2
    const centerY = top + height / 2

    const distX = e.clientX - centerX
    const distY = e.clientY - centerY

    if (Math.abs(distX) < distance && Math.abs(distY) < distance) {
      setPosition({ x: distX * magnetStrength, y: distY * magnetStrength })
    } else {
      setPosition({ x: 0, y: 0 })
    }
  }

  const handleMouseLeave = () => {
    setPosition({ x: 0, y: 0 })
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      animate={{ x: position.x, y: position.y }}
      transition={{ type: 'spring', damping: 15, stiffness: 200, mass: 0.1 }}
      className={`inline-block ${className}`}
    >
      {children}
    </motion.div>
  )
}
