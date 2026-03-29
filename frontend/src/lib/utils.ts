import { clsx, type ClassValue } from 'clsx'
import { formatDistanceToNow, parseISO } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return formatDistanceToNow(parseISO(iso), { addSuffix: true })
  } catch {
    return '—'
  }
}

export function sentimentLabel(score: number | null | undefined): 'positive' | 'negative' | 'neutral' {
  if (score == null) return 'neutral'
  if (score > 0.2) return 'positive'
  if (score < -0.2) return 'negative'
  return 'neutral'
}

export const PLATFORM_COLORS: Record<string, string> = {
  twitter: '#1DA1F2',
  instagram: '#E1306C',
  tiktok: '#010101',
}

export const TOPIC_COLORS: Record<string, string> = {
  fashion: '#ec4899',
  tech: '#3b82f6',
  food: '#f97316',
  music: '#8b5cf6',
  fitness: '#10b981',
  finance: '#f59e0b',
  travel: '#06b6d4',
  entertainment: '#ef4444',
  politics: '#6b7280',
  sports: '#84cc16',
}
