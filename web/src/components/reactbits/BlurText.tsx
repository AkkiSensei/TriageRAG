import React from 'react'
import { motion } from 'framer-motion'
import { useMotionOk } from '@/lib/motion'

interface BlurTextProps {
  text: string
  className?: string
  delay?: number
  animateBy?: 'words' | 'letters'
  direction?: 'top' | 'bottom'
}

export const BlurText: React.FC<BlurTextProps> = ({
  text,
  className = '',
  delay = 0.05,
  animateBy = 'words',
  direction = 'top',
}) => {
  const motionOk = useMotionOk()

  if (!motionOk) {
    return <span className={className}>{text}</span>
  }

  const elements = animateBy === 'words' ? text.split(' ') : text.split('')

  return (
    <span className={`inline-block ${className}`} aria-label={text}>
      {elements.map((element, index) => (
        <motion.span
          key={index}
          initial={{
            filter: 'blur(8px)',
            opacity: 0,
            y: direction === 'top' ? -10 : 10,
          }}
          animate={{
            filter: 'blur(0px)',
            opacity: 1,
            y: 0,
          }}
          transition={{
            duration: 0.5,
            delay: index * delay,
            ease: 'easeOut',
          }}
          className="inline-block"
        >
          {element}
          {animateBy === 'words' && index < elements.length - 1 ? '\u00A0' : ''}
        </motion.span>
      ))}
    </span>
  )
}
