'use client'

interface SyncBadgeProps {
  timestamp?: string | null
}

function fmt(ts: string): string {
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ts
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  const hm = d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false })
  if (sameDay) return `${hm} 기준`
  const md = `${d.getMonth() + 1}/${d.getDate()}`
  return `${md} ${hm} 기준`
}

export function SyncBadge({ timestamp }: SyncBadgeProps) {
  if (!timestamp) return null
  return (
    <span className="text-xs text-muted-foreground font-normal ml-2">
      {fmt(timestamp)}
    </span>
  )
}
