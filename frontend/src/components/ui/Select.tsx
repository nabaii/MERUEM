import { cn } from '../../lib/utils'
import type { SelectHTMLAttributes } from 'react'

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
}

export function Select({ label, className, id, children, ...props }: Props) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-slate-300">
          {label}
        </label>
      )}
      <select
        id={id}
        className={cn(
          'bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-slate-100',
          'focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500',
          'text-sm transition-colors',
          className,
        )}
        {...props}
      >
        {children}
      </select>
    </div>
  )
}
