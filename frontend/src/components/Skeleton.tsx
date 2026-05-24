import React from 'react'

interface SkeletonProps {
  className?: string
}

export const Skeleton: React.FC<SkeletonProps> = ({ className = '' }) => (
  <div className={`skeleton bg-gray-100 dark:bg-white/[0.04] rounded-md ${className}`} />
)

export const SkeletonText: React.FC<{ lines?: number; className?: string }> = ({ lines = 1, className = '' }) => (
  <div className={`space-y-1.5 ${className}`}>
    {Array.from({ length: lines }).map((_, i) => (
      <Skeleton key={i} className={`h-3 ${i === lines - 1 && lines > 1 ? 'w-3/4' : 'w-full'}`} />
    ))}
  </div>
)

export const SkeletonKpi: React.FC = () => (
  <div className="kpi space-y-3">
    <Skeleton className="h-2.5 w-16" />
    <Skeleton className="h-7 w-28" />
    <Skeleton className="h-2.5 w-20" />
  </div>
)

export const SkeletonRow: React.FC<{ avatar?: boolean }> = ({ avatar = false }) => (
  <div className="flex items-center gap-3 py-2.5">
    {avatar && <Skeleton className="w-8 h-8 rounded-full shrink-0" />}
    <div className="flex-1 space-y-1.5 min-w-0">
      <Skeleton className="h-3 w-1/3" />
      <Skeleton className="h-2.5 w-1/2" />
    </div>
    <Skeleton className="h-6 w-16 shrink-0" />
  </div>
)

export const SkeletonCard: React.FC<{ rows?: number }> = ({ rows = 4 }) => (
  <div className="card space-y-3">
    <Skeleton className="h-4 w-32 mb-2" />
    {Array.from({ length: rows }).map((_, i) => <SkeletonRow key={i} />)}
  </div>
)
