import React from 'react'
import { useMotionOk } from '@/lib/motion'

interface ShinyTextProps {
  text: string
  disabled?: boolean
  speed?: number
  className?: string
}

export const ShinyText: React.FC<ShinyTextProps> = ({
  text,
  disabled = false,
  speed = 4,
  className = '',
}) => {
  const motionOk = useMotionOk()

  if (!motionOk || disabled) {
    return <span className={`text-teal-400 font-semibold ${className}`}>{text}</span>
  }

  const animationDuration = `${speed}s`

  return (
    <span
      className={`inline-block bg-clip-text text-transparent bg-gradient-to-r from-slate-300 via-teal-300 to-slate-300 bg-[length:200%_100%] animate-shine ${className}`}
      style={{
        animation: `shine ${animationDuration} linear infinite`,
      }}
    >
      <style>
        {`
          @keyframes shine {
            0% { background-position: 200% 0; }
            100% { background-position: -200% 0; }
          }
        `}
      </style>
      {text}
    </span>
  )
}
