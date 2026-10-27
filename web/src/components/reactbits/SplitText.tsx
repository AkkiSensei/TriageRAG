import React from 'react'
import { motion } from 'framer-motion'
import { useMotionOk } from '@/lib/motion'

interface SplitTextProps {
  text: string
  className?: string
  delay?: number
  duration?: number
  splitBy?: 'words' | 'chars'
}

export const SplitText: React.FC<SplitTextProps> = ({
  text,
  className = '',
  delay = 0.05,
  duration = 0.4,
  splitBy = 'words',
}) => {
  const motionOk = useMotionOk()

  if (!motionOk) {
    return <span className={className}>{text}</span>
  }

  const items = splitBy === 'words' ? text.split(' ') : text.split('')

  return (
    <span className={`inline-block ${className}`} aria-label={text}>
      {items.map((item, index) => (
        <motion.span
          key={`${item}-${index}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration,
            delay: index * delay,
            ease: [0.2, 0.65, 0.3, 0.9],
          }}
          className="inline-block"
        >
          {item}
          {splitBy === 'words' && index < items.length - 1 ? '\u00A0' : ''}
        </motion.span>
      ))}
    </span>
  )
}
