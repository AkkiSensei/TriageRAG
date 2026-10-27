import React, { useEffect, useState } from 'react'
import { useMotionOk } from '@/lib/motion'

interface CountUpProps {
  to: number
  from?: number
  duration?: number
  decimals?: number
  suffix?: string
  prefix?: string
  className?: string
}

export const CountUp: React.FC<CountUpProps> = ({
  to,
  from = 0,
  duration = 1.2,
  decimals = 0,
  suffix = '',
  prefix = '',
  className = '',
}) => {
  const [count, setCount] = useState<number>(from)
  const motionOk = useMotionOk()

  useEffect(() => {
    if (!motionOk) {
      setCount(to)
      return
    }

    let startTimestamp: number | null = null
    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp
      const progress = Math.min((timestamp - startTimestamp) / (duration * 1000), 1)
      // Ease out cubic
      const easeProgress = 1 - Math.pow(1 - progress, 3)
      setCount(from + (to - from) * easeProgress)

      if (progress < 1) {
        requestAnimationFrame(step)
      } else {
        setCount(to)
      }
    }

    const frameId = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frameId)
  }, [to, from, duration, motionOk])

  const formatted = count.toFixed(decimals)

  return (
    <span className={`tabular-nums ${className}`}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  )
}
