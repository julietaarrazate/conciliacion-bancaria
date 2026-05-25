import React from 'react'

export interface BarSeries {
  label: string
  color: string
  data: number[]
}

interface BarChartProps {
  labels: string[]
  series: BarSeries[]
  height?: number
  formatValue?: (n: number) => string
}

const fmtDefault = (n: number) =>
  new Intl.NumberFormat('es-AR', { notation: 'compact', maximumFractionDigits: 1 }).format(n)

export const BarChart: React.FC<BarChartProps> = ({
  labels,
  series,
  height = 200,
  formatValue = fmtDefault,
}) => {
  const width = 600
  const padding = { top: 10, right: 12, bottom: 28, left: 8 }
  const innerW = width - padding.left - padding.right
  const innerH = height - padding.top - padding.bottom

  const allVals = series.flatMap(s => s.data)
  const maxV = Math.max(1, ...allVals)

  if (!labels.length || !series.length) {
    return <div className="text-sm text-gray-400 dark:text-zinc-500 text-center py-8">Sin datos</div>
  }

  const groupWidth = innerW / labels.length
  const barGap = 4
  const barWidth = Math.max(2, (groupWidth - barGap * (series.length + 1)) / series.length)

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="none">
        {/* eje X */}
        <line x1={padding.left} y1={padding.top + innerH} x2={width - padding.right} y2={padding.top + innerH}
          stroke="currentColor" strokeOpacity={0.15} strokeWidth={1} />
        {labels.map((label, i) => {
          const xGroup = padding.left + i * groupWidth
          return (
            <g key={i}>
              {series.map((s, j) => {
                const v = s.data[i] || 0
                const h = (v / maxV) * innerH
                const x = xGroup + barGap + j * (barWidth + barGap)
                const y = padding.top + innerH - h
                return (
                  <g key={j}>
                    <rect
                      x={x}
                      y={y}
                      width={barWidth}
                      height={h}
                      fill={s.color}
                      rx={2}
                    >
                      <title>{`${label} · ${s.label}: ${formatValue(v)}`}</title>
                    </rect>
                  </g>
                )
              })}
              <text x={xGroup + groupWidth / 2} y={height - 12} textAnchor="middle" fontSize={10} fill="currentColor" className="text-gray-500 dark:text-zinc-500">
                {label}
              </text>
            </g>
          )
        })}
      </svg>
      {series.length > 1 && (
        <div className="flex flex-wrap gap-3 mt-2 justify-center">
          {series.map((s, i) => (
            <div key={i} className="flex items-center gap-1.5 text-xs">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ background: s.color }} />
              <span className="text-ml-text-soft dark:text-zinc-400">{s.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
