import React, { useMemo, useState } from 'react'

export interface LinePoint {
  label: string
  value: number
}

interface LineChartProps {
  data: LinePoint[]
  height?: number
  color?: string
  fillColor?: string
  showLabels?: boolean
  formatValue?: (n: number) => string
}

const fmtDefault = (n: number) =>
  new Intl.NumberFormat('es-AR', { notation: 'compact', maximumFractionDigits: 1 }).format(n)

export const LineChart: React.FC<LineChartProps> = ({
  data,
  height = 180,
  color = '#10b981',
  fillColor,
  showLabels = true,
  formatValue = fmtDefault,
}) => {
  const [hover, setHover] = useState<number | null>(null)

  const width = 600
  const padding = { top: 10, right: 12, bottom: showLabels ? 24 : 8, left: 8 }
  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom

  const { minV, maxV } = useMemo(() => {
    if (!data.length) return { minV: 0, maxV: 1 }
    const vals = data.map(d => d.value)
    const min = Math.min(0, ...vals)
    const max = Math.max(...vals, 1)
    return { minV: min, maxV: max === min ? min + 1 : max }
  }, [data])

  if (!data.length) {
    return <div className="text-sm text-gray-400 dark:text-zinc-500 text-center py-8">Sin datos</div>
  }

  const xStep = data.length > 1 ? innerW / (data.length - 1) : 0
  const points = data.map((d, i) => {
    const x = padding.left + (data.length === 1 ? innerW / 2 : i * xStep)
    const y = padding.top + innerH - ((d.value - minV) / (maxV - minV)) * innerH
    return { x, y, ...d }
  })

  const pathLine = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
  const pathFill = `${pathLine} L ${points[points.length - 1].x} ${padding.top + innerH} L ${points[0].x} ${padding.top + innerH} Z`

  return (
    <div className="w-full relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="none">
        <path d={pathFill} fill={fillColor || color} fillOpacity={0.12} />
        <path d={pathLine} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        {points.map((p, i) => (
          <g key={i}>
            <circle
              cx={p.x}
              cy={p.y}
              r={hover === i ? 5 : 3}
              fill="white"
              stroke={color}
              strokeWidth={2}
              style={{ transition: 'r 100ms' }}
            />
            <rect
              x={p.x - xStep / 2}
              y={padding.top}
              width={xStep || innerW}
              height={innerH}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            />
            {showLabels && (
              <text x={p.x} y={height - 6} textAnchor="middle" fontSize={10} fill="currentColor" className="text-gray-500 dark:text-zinc-500">
                {p.label}
              </text>
            )}
          </g>
        ))}
      </svg>
      {hover !== null && (
        <div
          className="absolute pointer-events-none bg-ml-text dark:bg-white text-white dark:text-ml-text px-2 py-1 rounded text-xs font-medium shadow-md whitespace-nowrap"
          style={{
            left: `${(points[hover].x / width) * 100}%`,
            top: `${((points[hover].y - 30) / height) * 100}%`,
            transform: 'translateX(-50%)',
          }}
        >
          {points[hover].label}: {formatValue(points[hover].value)}
        </div>
      )}
    </div>
  )
}
