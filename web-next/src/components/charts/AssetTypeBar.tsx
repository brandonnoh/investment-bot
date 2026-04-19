'use client'
import type { PriceItem } from '@/types/api'

const ASSET_COLORS: Record<string, string> = {
  '주식': '#c9a93a',
  '코인': '#4ec9b0',
  '금':   '#e09b3d',
  '부동산': '#4dca7e',
  '기타':  '#9a8e84',
}

function classifyAsset(h: PriceItem): string {
  const market = (h.market ?? '').toUpperCase()
  const sector = (h.sector ?? '').toLowerCase()
  const ticker = (h.ticker ?? '').toUpperCase()
  const cryptoTickers = ['BTC', 'ETH', 'XRP', 'SOL', 'BNB', 'DOGE', 'ADA']
  if (market.includes('CRYPTO') || cryptoTickers.some(t => ticker.includes(t))) return '코인'
  if (sector.includes('금') || ['GLD', 'IAU', 'GOLD'].some(t => ticker.includes(t))) return '금'
  if (market.includes('REIT') || sector.includes('부동산')) return '부동산'
  return '주식'
}

interface AssetEntry { name: string; value: number }

export function AssetTypeBar({ holdings }: { holdings: PriceItem[] }) {
  const assetMap: Record<string, number> = {}
  holdings.forEach(h => {
    const key = classifyAsset(h)
    assetMap[key] = (assetMap[key] ?? 0) + (h.current_value_krw ?? 1)
  })
  const data: AssetEntry[] = Object.entries(assetMap)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name, value }))
  const total = data.reduce((s, d) => s + d.value, 0)

  if (data.length === 0) return null

  return (
    <div className="space-y-3">
      <div className="flex h-6 rounded-md overflow-hidden gap-px">
        {data.map(entry => (
          <div
            key={entry.name}
            style={{
              width: `${(entry.value / total) * 100}%`,
              backgroundColor: ASSET_COLORS[entry.name] ?? '#9a8e84',
            }}
            title={`${entry.name} ${((entry.value / total) * 100).toFixed(1)}%`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1.5">
        {data.map(entry => (
          <span key={entry.name} className="flex items-center gap-1">
            <span
              style={{ backgroundColor: ASSET_COLORS[entry.name] ?? '#9a8e84' }}
              className="inline-block w-2 h-2 rounded-sm shrink-0"
            />
            <span className="text-[11px] text-muted-foreground whitespace-nowrap">
              {entry.name} <span className="text-foreground font-mono">{((entry.value / total) * 100).toFixed(0)}%</span>
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}
