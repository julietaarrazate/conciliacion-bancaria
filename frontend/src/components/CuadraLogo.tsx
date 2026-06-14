import React, { useEffect, useState } from 'react'

interface CuadraLogoProps {
  size?: number
  animate?: boolean
  surfaceColor?: string
  trackColor?: string
  fillColor?: string
  dotColor?: string
  className?: string
}

const ARC_LENGTH = 197
const ARC_REST = 50

export const CuadraLogo: React.FC<CuadraLogoProps> = ({
  size = 32,
  animate = true,
  surfaceColor = '#16161C',
  trackColor = '#2A2A35',
  fillColor = '#22C55E',
  dotColor = '#5E6AD2',
  className = '',
}) => {
  const [offset, setOffset] = useState(animate ? ARC_LENGTH : ARC_REST)
  const [hover, setHover] = useState(false)

  useEffect(() => {
    if (!animate) return
    const t = setTimeout(() => setOffset(ARC_REST), 80)
    return () => clearTimeout(t)
  }, [animate])

  const effectiveOffset = hover ? 0 : offset

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 128 128"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <rect width="128" height="128" rx="28" fill={surfaceColor} />
      <path
        d="M95 36 A42 42 0 1 0 95 92"
        stroke={trackColor}
        strokeWidth="14"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M95 36 A42 42 0 1 0 95 92"
        stroke={fillColor}
        strokeWidth="14"
        strokeLinecap="round"
        fill="none"
        strokeDasharray={ARC_LENGTH}
        strokeDashoffset={effectiveOffset}
        style={{ transition: 'stroke-dashoffset 700ms cubic-bezier(0.4, 0, 0.2, 1)' }}
      />
      <circle
        cx="95"
        cy="92"
        r="8"
        fill={dotColor}
        style={{
          transition: 'transform 400ms cubic-bezier(0.4, 0, 0.2, 1)',
          transformOrigin: '95px 92px',
          transform: hover ? 'scale(1.25)' : 'scale(1)',
        }}
      />
    </svg>
  )
}
