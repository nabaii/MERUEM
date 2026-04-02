import { useState, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { cn } from '../../lib/utils'

interface Props {
  tags: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
  label?: string
  maxTags?: number
  disabled?: boolean
  className?: string
}

export function KeywordTagInput({
  tags,
  onChange,
  placeholder = 'Type and press Enter…',
  label,
  maxTags = 30,
  disabled = false,
  className,
}: Props) {
  const [input, setInput] = useState('')

  const addTag = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return
    if (tags.includes(trimmed)) return
    if (tags.length >= maxTags) return
    onChange([...tags, trimmed])
    setInput('')
  }

  const removeTag = (index: number) => {
    onChange(tags.filter((_, i) => i !== index))
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTag(input)
    }
    if (e.key === 'Backspace' && input === '' && tags.length > 0) {
      removeTag(tags.length - 1)
    }
  }

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {label && (
        <label className="text-sm font-medium text-slate-300">{label}</label>
      )}
      <div
        className={cn(
          'flex flex-wrap items-center gap-1.5 rounded-lg border px-3 py-2',
          'bg-slate-700 border-slate-600 transition-colors',
          'focus-within:ring-2 focus-within:ring-brand-500 focus-within:border-brand-500',
          disabled && 'opacity-50 cursor-not-allowed',
        )}
      >
        {tags.map((tag, i) => (
          <span
            key={`${tag}-${i}`}
            className={cn(
              'inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium',
              'bg-brand-600/20 text-brand-300 border border-brand-500/30',
              'animate-in fade-in duration-200',
            )}
          >
            {tag}
            {!disabled && (
              <button
                type="button"
                onClick={() => removeTag(i)}
                className="ml-0.5 rounded-full p-0.5 hover:bg-brand-500/30 transition-colors"
              >
                <X size={12} />
              </button>
            )}
          </span>
        ))}
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={tags.length === 0 ? placeholder : ''}
          disabled={disabled}
          className={cn(
            'flex-1 min-w-[120px] bg-transparent border-none outline-none',
            'text-sm text-slate-100 placeholder:text-slate-500',
          )}
        />
      </div>
      {tags.length > 0 && (
        <p className="text-xs text-slate-500">
          {tags.length} keyword{tags.length !== 1 ? 's' : ''}
          {maxTags < 30 ? ` (max ${maxTags})` : ''}
        </p>
      )}
    </div>
  )
}
