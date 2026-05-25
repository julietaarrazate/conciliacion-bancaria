import React from 'react'

export interface DonutSlice {
  label: string
  value: number
  color: string
}

interface DonutChartProps {
  data: DonutSlice[]
  size?: number
  thickness?: number
  centerLabel?: string
  centerSubLabel?: string
  showLegend?: boolean
  formatValue?: (n: number) => string
}

const fmtDefault = (n: number) =>
  new Intl.NumberFormat('es-AR', { notation: 'compact', maximumFractionDigits: 1 }).format(n)

export const DonutChart: React.FC<DonutChartProps> = ({
  data,
  size = 160,
  thickness = 22,
  centerLabel,
  centerSubLabel,
  showLegend = true,
  formatValue = fmtDefault,
}) => {
  const total = data.reduce((s, d) => s + d.value, 0)
  if (total === 0) {
    return <div className="text-sm text-gray-400 dark:text-zinc-500 text-center py-8">Sin datos</div>
  }

  const radius = (size - thickness) / 2
  const cx = size / 2
  const cy = size / 2
  const circumference = 2 * Math.PI * radius

  let offset = 0
  const segments = data.map((d) => {
    const pct = d.value / total
    const dashArray = `${pct * circumference} ${circumference}`
    const seg = {
      label: d.label,
      value: d.value,
      color: d.color,
      pct,
      dashArray,
      dashOffset: -offset * circumference,
    }
    offset += pct
    return seg
  })

  return (
    <div className={`flex ${showLegend ? 'items-center gap-4 flex-col sm:flex-row' : ''}`}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
          <circle cx={cx} cy={cy} r={radius} fill="none" stroke="currentColor" strokeOpacity={0.08} strokeWidth={thickness} />
          {segments.map((s, i) => (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r={radius}
              fill="none"
              stroke={s.color}
              strokeWidth={thickness}
              strokeDasharray={s.dashArray}
              strokeDashoffset={s.dashOffset}
              strokeLinecap="butt"
            />
          ))}
        </svg>
        {(centerLabel || centerSubLabel) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            {centerLabel && <div className="text-lg font-bold text-ml-text dark:text-white leading-tight">{centerLabel}</div>}
            {centerSubLabel && <div className="text-[10px] text-gray-500 dark:text-zinc-500 uppercase tracking-wide">{centerSubLabel}</div>}
          </div>
        )}
      </div>
      {showLegend && (
        <div className="flex-1 space-y-1.5 min-w-0">
          {segments.map((s, i) => (
            <div key={i} className="flex items-center gap-2 text-xs min-w-0">
              <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: s.color }} />
              <span className="text-ml-text dark:text-zinc-300 truncate flex-1">{s.label}</span>
              <span className="font-mono text-ml-text-soft dark:text-zinc-500 whitespace-nowrap">{formatValue(s.value)}</span>
              <span className="font-mono text-ml-text-soft dark:text-zinc-500 w-10 text-right">{(s.pct * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
