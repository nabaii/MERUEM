import { cn } from '../../lib/utils'
import type { InputHTMLAttributes } from 'react'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export function Input({ label, error, className, id, ...props }: Props) {
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-slate-300">
          {label}
        </label>
      )}
      <input
        id={id}
        className={cn(
          'bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-slate-100',
          'placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500',
          'focus:border-brand-500 transition-colors text-sm',
          error && 'border-red-500',
          className,
        )}
        {...props}
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}
