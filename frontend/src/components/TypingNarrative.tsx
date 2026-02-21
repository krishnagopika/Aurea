'use client'

import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

interface TypingNarrativeProps {
  text: string
  wordsPerSecond?: number
  onComplete?: () => void
  className?: string
}

export default function TypingNarrative({
  text,
  wordsPerSecond = 10,
  onComplete,
  className,
}: TypingNarrativeProps) {
  const [displayedText, setDisplayedText] = useState('')
  const [isComplete, setIsComplete] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const indexRef = useRef(0)

  const words = text.split(' ')
  const intervalMs = Math.max(50, Math.round(1000 / wordsPerSecond))

  useEffect(() => {
    // Reset
    setDisplayedText('')
    setIsComplete(false)
    indexRef.current = 0

    if (!text) return

    intervalRef.current = setInterval(() => {
      if (indexRef.current < words.length) {
        const word = words[indexRef.current]
        setDisplayedText((prev) =>
          prev ? `${prev} ${word}` : word,
        )
        indexRef.current++
      } else {
        if (intervalRef.current) clearInterval(intervalRef.current)
        setIsComplete(true)
        onComplete?.()
      }
    }, intervalMs)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    // words array changes reference each render - intentionally only re-run when text changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, intervalMs])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className={className}
    >
      <p className="text-sm leading-relaxed text-slate-700 relative">
        {displayedText || (
          <span className="inline-block">
            <span className="sr-only">Loading narrative...</span>
          </span>
        )}
        {/* Blinking cursor */}
        {!isComplete && (
          <span
            className="inline-block ml-0.5 w-0.5 h-4 bg-blue-600 animate-blink align-middle"
            aria-hidden="true"
          />
        )}
      </p>
    </motion.div>
  )
}
