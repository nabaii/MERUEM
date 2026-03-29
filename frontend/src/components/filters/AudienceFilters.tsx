import { useQuery } from '@tanstack/react-query'
import { clustersApi } from '../../api/clusters'
import type { ProfileFilters } from '../../api/profiles'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { Button } from '../ui/Button'
import { Search, X } from 'lucide-react'

const TOPICS = [
  'fashion', 'tech', 'food', 'music', 'fitness',
  'finance', 'travel', 'entertainment', 'politics', 'sports',
]

interface Props {
  filters: ProfileFilters
  onChange: (f: ProfileFilters) => void
  onReset: () => void
}

export function AudienceFilters({ filters, onChange, onReset }: Props) {
  const { data: clustersData } = useQuery({
    queryKey: ['clusters'],
    queryFn: () => clustersApi.list(),
  })

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">Filters</h3>
        <button onClick={onReset} className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1">
          <X size={12} /> Reset
        </button>
      </div>

      <div className="relative">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
        <input
          value={filters.q ?? ''}
          onChange={(e) => onChange({ ...filters, q: e.target.value || undefined, offset: 0 })}
          placeholder="Search name or username…"
          className="w-full bg-slate-700 border border-slate-600 rounded-lg pl-8 pr-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>

      <Select
        label="Platform"
        value={filters.platform ?? ''}
        onChange={(e) => onChange({ ...filters, platform: e.target.value || undefined, offset: 0 })}
      >
        <option value="">All platforms</option>
        <option value="twitter">Twitter / X</option>
        <option value="instagram">Instagram</option>
        <option value="tiktok">TikTok</option>
      </Select>

      <Select
        label="Interest topic"
        value={filters.interest ?? ''}
        onChange={(e) => onChange({ ...filters, interest: e.target.value || undefined, offset: 0 })}
      >
        <option value="">Any topic</option>
        {TOPICS.map((t) => (
          <option key={t} value={t} className="capitalize">{t}</option>
        ))}
      </Select>

      <Select
        label="Cluster"
        value={filters.cluster_id ?? ''}
        onChange={(e) =>
          onChange({ ...filters, cluster_id: e.target.value ? Number(e.target.value) : undefined, offset: 0 })
        }
      >
        <option value="">Any cluster</option>
        {clustersData?.items.map((c) => (
          <option key={c.id} value={c.id}>{c.label ?? `Cluster ${c.id}`}</option>
        ))}
      </Select>

      <Input
        label="Location"
        value={filters.location ?? ''}
        onChange={(e) => onChange({ ...filters, location: e.target.value || undefined, offset: 0 })}
        placeholder="e.g. Lagos"
      />

      <div className="grid grid-cols-2 gap-2">
        <Input
          label="Min followers"
          type="number"
          min={0}
          value={filters.min_followers ?? ''}
          onChange={(e) =>
            onChange({ ...filters, min_followers: e.target.value ? Number(e.target.value) : undefined, offset: 0 })
          }
          placeholder="0"
        />
        <Input
          label="Max followers"
          type="number"
          min={0}
          value={filters.max_followers ?? ''}
          onChange={(e) =>
            onChange({ ...filters, max_followers: e.target.value ? Number(e.target.value) : undefined, offset: 0 })
          }
          placeholder="∞"
        />
      </div>
    </div>
  )
}
