import { cn } from '../../lib/utils'
import type { HTMLAttributes } from 'react'

type Color = 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'gray' | 'pink' | 'cyan'

const colors: Record<Color, string> = {
  blue:   'bg-blue-900/50 text-blue-300 border-blue-700',
  green:  'bg-emerald-900/50 text-emerald-300 border-emerald-700',
  red:    'bg-red-900/50 text-red-300 border-red-700',
  yellow: 'bg-yellow-900/50 text-yellow-300 border-yellow-700',
  purple: 'bg-purple-900/50 text-purple-300 border-purple-700',
  gray:   'bg-slate-700/50 text-slate-300 border-slate-600',
  pink:   'bg-pink-900/50 text-pink-300 border-pink-700',
  cyan:   'bg-cyan-900/50 text-cyan-300 border-cyan-700',
}

interface Props extends HTMLAttributes<HTMLSpanElement> {
  color?: Color
}

export function Badge({ color = 'gray', className, children, ...props }: Props) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border',
        colors[color],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  )
}
