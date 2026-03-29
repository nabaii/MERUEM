/**
 * Campaign Builder — filter profiles, estimate reach, save as a campaign.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Users, Zap } from 'lucide-react'
import toast from 'react-hot-toast'
import { campaignsApi, ReachFilters } from '../api/campaigns'
import { Spinner } from '../components/ui/Spinner'

const PLATFORMS = ['twitter', 'instagram', 'facebook', 'tiktok', 'youtube']

export function CampaignBuilderPage() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [filters, setFilters] = useState<ReachFilters>({})

  const { data: estimate, isLoading: estimating } = useQuery({
    queryKey: ['reach-estimate', filters],
    queryFn: () => campaignsApi.reachEstimate(filters),
    enabled: Object.values(filters).some((v) => v !== undefined && v !== ''),
  })

  const createMutation = useMutation({
    mutationFn: () =>
      campaignsApi.create({
        name: name.trim(),
        filters: filters as Record<string, unknown>,
      }),
    onSuccess: (c) => {
      toast.success('Campaign created')
      navigate(`/campaigns/${c.id}`)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  function setFilter<K extends keyof ReachFilters>(key: K, value: ReachFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value || undefined }))
  }

  return (
    <div className="flex-1 p-6 max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Campaign Builder</h1>
        <p className="text-sm text-slate-400 mt-0.5">
          Define your audience filters and create a campaign.
        </p>
      </div>

      {/* Campaign name */}
      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Campaign Name
        </label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Q3 Lagos Music Fans"
          className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>

      {/* Filters */}
      <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-slate-100">Audience Filters</h2>

        <div className="grid grid-cols-2 gap-4">
          {/* Platform */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-400">Platform</label>
            <select
              value={filters.platform ?? ''}
              onChange={(e) => setFilter('platform', e.target.value || undefined)}
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="">Any</option>
              {PLATFORMS.map((p) => (
                <option key={p} value={p} className="capitalize">
                  {p}
                </option>
              ))}
            </select>
          </div>

          {/* Location */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-400">Location (contains)</label>
            <input
              value={filters.location ?? ''}
              onChange={(e) => setFilter('location', e.target.value || undefined)}
              placeholder="e.g. Lagos"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>

          {/* Min followers */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-400">Min Followers</label>
            <input
              type="number"
              min={0}
              value={filters.min_followers ?? ''}
              onChange={(e) =>
                setFilter('min_followers', e.target.value ? Number(e.target.value) : undefined)
              }
              placeholder="0"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>

          {/* Max followers */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-400">Max Followers</label>
            <input
              type="number"
              min={0}
              value={filters.max_followers ?? ''}
              onChange={(e) =>
                setFilter('max_followers', e.target.value ? Number(e.target.value) : undefined)
              }
              placeholder="No limit"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
        </div>
      </div>

      {/* Reach estimate */}
      <div className="flex items-center gap-3 bg-slate-800/40 border border-slate-700/60 rounded-xl px-5 py-4">
        <Users size={20} className="text-brand-400 flex-shrink-0" />
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">
            Estimated Reach
          </p>
          {estimating ? (
            <Spinner className="mt-0.5" />
          ) : (
            <p className="text-2xl font-bold text-slate-100 leading-none mt-0.5">
              {estimate
                ? estimate.estimated_profiles.toLocaleString()
                : '—'}
            </p>
          )}
        </div>
      </div>

      {/* Create button */}
      <button
        disabled={!name.trim() || createMutation.isPending}
        onClick={() => createMutation.mutate()}
        className="flex items-center justify-center gap-2 w-full py-3 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold rounded-xl transition-colors"
      >
        {createMutation.isPending ? (
          <Spinner className="text-white" />
        ) : (
          <Zap size={16} />
        )}
        Create Campaign
      </button>
    </div>
  )
}
