import React, { useRef, useEffect } from 'react'
import { useMotionOk } from '@/lib/motion'

interface Spark {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  color: string
  opacity: number
}

interface ClickSparkProps {
  children: React.ReactNode
  sparkColor?: string
  sparkCount?: number
  className?: string
}

export const ClickSpark: React.FC<ClickSparkProps> = ({
  children,
  sparkColor = '#14b8a6',
  sparkCount = 8,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const sparksRef = useRef<Spark[]>([])
  const motionOk = useMotionOk()

  useEffect(() => {
    if (!motionOk) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationId: number

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      sparksRef.current = sparksRef.current.filter((s) => s.opacity > 0)

      for (const s of sparksRef.current) {
        s.x += s.vx
        s.y += s.vy
        s.opacity -= 0.04

        ctx.beginPath()
        ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2)
        ctx.fillStyle = s.color
        ctx.globalAlpha = Math.max(0, s.opacity)
        ctx.fill()
      }

      if (sparksRef.current.length > 0) {
        animationId = requestAnimationFrame(render)
      }
    }

    const handleClick = (e: MouseEvent) => {
      if (!canvas || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      canvas.width = rect.width
      canvas.height = rect.height

      const clickX = e.clientX - rect.left
      const clickY = e.clientY - rect.top

      for (let i = 0; i < sparkCount; i++) {
        const angle = Math.random() * Math.PI * 2
        const speed = Math.random() * 2 + 1
        sparksRef.current.push({
          x: clickX,
          y: clickY,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          size: Math.random() * 2 + 1,
          color: sparkColor,
          opacity: 1,
        })
      }

      cancelAnimationFrame(animationId)
      animationId = requestAnimationFrame(render)
    }

    const container = containerRef.current
    if (container) {
      container.addEventListener('click', handleClick)
    }

    return () => {
      if (container) {
        container.removeEventListener('click', handleClick)
      }
      cancelAnimationFrame(animationId)
    }
  }, [motionOk, sparkColor, sparkCount])

  return (
    <div ref={containerRef} className={`relative inline-block ${className}`}>
      {motionOk && (
        <canvas
          ref={canvasRef}
          className="pointer-events-none absolute inset-0 z-50 h-full w-full"
          aria-hidden="true"
        />
      )}
      {children}
    </div>
  )
}
