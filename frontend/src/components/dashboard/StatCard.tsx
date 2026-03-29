import { cn, formatNumber } from '../../lib/utils'
import type { LucideIcon } from 'lucide-react'

interface Props {
  label: string
  value: number | string
  icon: LucideIcon
  color?: 'blue' | 'green' | 'purple' | 'yellow'
  delta?: string
}

const colorMap = {
  blue:   { bg: 'bg-brand-600/15', icon: 'text-brand-400' },
  green:  { bg: 'bg-emerald-600/15', icon: 'text-emerald-400' },
  purple: { bg: 'bg-purple-600/15', icon: 'text-purple-400' },
  yellow: { bg: 'bg-yellow-600/15', icon: 'text-yellow-400' },
}

export function StatCard({ label, value, icon: Icon, color = 'blue', delta }: Props) {
  const c = colorMap[color]
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 flex items-center gap-4">
      <div className={cn('rounded-xl p-3', c.bg)}>
        <Icon size={22} className={c.icon} />
      </div>
      <div>
        <p className="text-sm text-slate-400">{label}</p>
        <p className="text-2xl font-bold text-slate-100 mt-0.5">
          {typeof value === 'number' ? formatNumber(value) : value}
        </p>
        {delta && <p className="text-xs text-emerald-400 mt-0.5">{delta}</p>}
      </div>
    </div>
  )
}
