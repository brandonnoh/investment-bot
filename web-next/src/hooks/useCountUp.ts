import { useEffect, useRef, useState } from 'react'

export function useCountUp(target: number | undefined, duration = 700): number {
  const [display, setDisplay] = useState(target ?? 0)
  const from = useRef(target ?? 0)
  const raf = useRef<number>(0)

  useEffect(() => {
    if (target === undefined) return
    const start = from.current
    const t0 = performance.now()
    cancelAnimationFrame(raf.current)
    raf.current = requestAnimationFrame(function tick(now) {
      const p = Math.min((now - t0) / duration, 1)
      const eased = 1 - Math.pow(1 - p, 4)
      setDisplay(start + (target - start) * eased)
      if (p < 1) raf.current = requestAnimationFrame(tick)
      else from.current = target
    })
    return () => cancelAnimationFrame(raf.current)
  }, [target, duration])

  return display
}

export function fgStyle(score: number | undefined) {
  if (score === undefined) return { color: 'text-muted-foreground', bar: 'bg-muted', pulse: false }
  if (score <= 25) return { color: 'text-mc-red', bar: 'bg-mc-red', pulse: true }
  if (score <= 45) return { color: 'text-amber', bar: 'bg-amber', pulse: false }
  return { color: 'text-mc-green', bar: 'bg-mc-green', pulse: false }
}
