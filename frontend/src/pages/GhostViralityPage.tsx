import { useState, type ReactNode } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Zap,
  Eye,
  TrendingUp,
  CheckCircle2,
  Loader,
  Plus,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { ghostViralityApi } from '../api/ghostVirality'
import { GhostFeed } from '../components/ghost/GhostFeed'
import { TrialReelTracker } from '../components/ghost/TrialReelTracker'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { PageSpinner } from '../components/ui/Spinner'

const STRATEGY_OPTIONS = [
  { value: '', label: 'All strategies' },
  { value: 'high_dm_share', label: 'High DM Share' },
  { value: 'watch_time_arbitrage', label: 'Watch Time Arb' },
  { value: 'audio_driven', label: 'Audio-Driven' },
  { value: 'polarizing', label: 'Polarizing' },
  { value: 'utility', label: 'Utility' },
]

const DAY_OPTIONS = [
  { value: 3, label: 'Last 3 days' },
  { value: 7, label: 'Last 7 days' },
  { value: 14, label: 'Last 14 days' },
  { value: 30, label: 'Last 30 days' },
]

export function GhostViralityPage() {
  const qc = useQueryClient()
  const [activeTab, setActiveTab] = useState<'feed' | 'trial' | 'niches'>('feed')
  const [filterNiche, setFilterNiche] = useState('')
  const [filterStrategy, setFilterStrategy] = useState('')
  const [filterDays, setFilterDays] = useState(7)
  const [showScoutForm, setShowScoutForm] = useState(false)
  const [scoutForm, setScoutForm] = useState({ niche: '', accounts: '' })

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['ghost-stats'],
    queryFn: ghostViralityApi.getStats,
    refetchInterval: 30_000,
  })

  const { data: posts = [], isLoading: postsLoading, refetch: refetchPosts } = useQuery({
    queryKey: ['ghost-feed', filterNiche, filterStrategy, filterDays],
    queryFn: () =>
      ghostViralityApi.listGhosts({
        niche: filterNiche || undefined,
        strategy: filterStrategy || undefined,
        days: filterDays,
        limit: 100,
      }),
  })

  const { data: niches = [], isLoading: nichesLoading } = useQuery({
    queryKey: ['ghost-niches'],
    queryFn: ghostViralityApi.listNiches,
  })

  const { data: scoutJobs = [] } = useQuery({
    queryKey: ['ghost-scout-jobs'],
    queryFn: () => ghostViralityApi.listScoutJobs(10),
    refetchInterval: 10_000,
  })

  const createScoutMut = useMutation({
    mutationFn: () =>
      ghostViralityApi.createScoutJob(
        scoutForm.niche,
        scoutForm.accounts.split(',').map(a => a.trim()).filter(Boolean),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ghost-scout-jobs'] })
      qc.invalidateQueries({ queryKey: ['ghost-stats'] })
      setShowScoutForm(false)
      setScoutForm({ niche: '', accounts: '' })
      toast.success('Scout job started')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  if (statsLoading) return <PageSpinner />

  const activeNiches = [...new Set(posts.map(p => p.niche).filter(Boolean))] as string[]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="rounded-lg bg-pink-900/40 p-2">
              <Zap size={18} className="text-pink-400" />
            </div>
            <h1 className="text-2xl font-bold text-slate-100">Ghost Virality</h1>
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Reels the algorithm is pushing despite low engagement — your arbitrage signal.
          </p>
        </div>
        <Button onClick={() => setShowScoutForm(v => !v)}>
          <Plus size={15} />
          New Scout Job
        </Button>
      </div>

      {/* Scout Job Form */}
      {showScoutForm && (
        <Card className="border-pink-500/20">
          <CardHeader>
            <CardTitle>Start Scout Job</CardTitle>
          </CardHeader>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="text-xs text-slate-500 mb-1 block">Niche *</label>
              <input
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500"
                placeholder="e.g. fitness, finance, beauty"
                value={scoutForm.niche}
                onChange={e => setScoutForm(f => ({ ...f, niche: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">Competitor accounts (comma-separated) *</label>
              <input
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500"
                placeholder="account1, account2, account3"
                value={scoutForm.accounts}
                onChange={e => setScoutForm(f => ({ ...f, accounts: e.target.value }))}
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <Button
              loading={createScoutMut.isPending}
              disabled={!scoutForm.niche || !scoutForm.accounts}
              onClick={() => createScoutMut.mutate()}
            >
              Start scouting
            </Button>
            <Button variant="secondary" onClick={() => setShowScoutForm(false)}>
              Cancel
            </Button>
          </div>
        </Card>
      )}

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <GhostStat icon={<Zap size={18} className="text-pink-400" />} label="Ghost Posts" value={stats.total_ghost_posts} bg="bg-pink-600/15" />
          <GhostStat icon={<TrendingUp size={18} className="text-yellow-400" />} label="New (7d)" value={stats.new_last_7_days} bg="bg-yellow-600/15" />
          <GhostStat icon={<Eye size={18} className="text-blue-400" />} label="Pattern Cards" value={stats.pattern_cards_ready} bg="bg-blue-600/15" />
          <GhostStat icon={<Loader size={18} className="text-purple-400" />} label="Active Scouts" value={stats.active_scout_jobs} bg="bg-purple-600/15" />
          <GhostStat icon={<TrendingUp size={18} className="text-cyan-400" />} label="Trial Reels" value={stats.trial_reels_total} bg="bg-cyan-600/15" />
          <GhostStat icon={<CheckCircle2 size={18} className="text-emerald-400" />} label="Green Lit" value={stats.trial_reels_green_lit} bg="bg-emerald-600/15" />
        </div>
      )}

      {/* Scout jobs status strip */}
      {scoutJobs.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {scoutJobs.slice(0, 5).map(job => (
            <div
              key={job.id}
              className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs"
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  job.status === 'running'
                    ? 'bg-blue-400 animate-pulse'
                    : job.status === 'completed'
                    ? 'bg-emerald-400'
                    : job.status === 'failed'
                    ? 'bg-red-400'
                    : 'bg-slate-500'
                }`}
              />
              <span className="text-slate-300 font-medium">{job.niche}</span>
              <span className="text-slate-500">{job.ghost_viral_found} found</span>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-700">
        {(['feed', 'trial', 'niches'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? 'border-pink-500 text-pink-400'
                : 'border-transparent text-slate-500 hover:text-slate-300'
            }`}
          >
            {tab === 'feed' ? 'Ghost Feed' : tab === 'trial' ? 'Trial Reels' : 'Niches'}
          </button>
        ))}
      </div>

      {/* Ghost Feed */}
      {activeTab === 'feed' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <select
              className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={filterNiche}
              onChange={e => setFilterNiche(e.target.value)}
            >
              <option value="">All niches</option>
              {activeNiches.map(n => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
            <select
              className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={filterStrategy}
              onChange={e => setFilterStrategy(e.target.value)}
            >
              {STRATEGY_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <select
              className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={filterDays}
              onChange={e => setFilterDays(Number(e.target.value))}
            >
              {DAY_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <Button variant="secondary" size="sm" onClick={() => refetchPosts()}>
              <RefreshCw size={13} />
              Refresh
            </Button>
          </div>

          <Card>
            <GhostFeed posts={posts} loading={postsLoading} />
          </Card>
        </div>
      )}

      {/* Trial Reels */}
      {activeTab === 'trial' && (
        <TrialReelTracker niche={filterNiche || undefined} />
      )}

      {/* Niche Heatmap */}
      {activeTab === 'niches' && (
        <div className="space-y-4">
          {nichesLoading ? (
            <p className="text-slate-500 text-sm">Loading niches…</p>
          ) : niches.length === 0 ? (
            <Card>
              <p className="text-center text-slate-500 py-8 text-sm">
                No niche data yet — run scout jobs to start building percentile distributions.
              </p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {niches.map(niche => (
                <Card key={niche.niche} className="hover:border-pink-500/30 transition-colors">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-slate-200 capitalize">{niche.niche}</h3>
                    <Badge color="pink">{niche.ghost_viral_count ?? 0} posts</Badge>
                  </div>
                  <div className="space-y-2 text-xs">
                    <PercentileBar label="P10" value={niche.p10} max={niche.p90} />
                    <PercentileBar label="P30" value={niche.p30} max={niche.p90} />
                    <PercentileBar label="P50" value={niche.p50} max={niche.p90} />
                    <PercentileBar label="P70" value={niche.p70} max={niche.p90} />
                    <PercentileBar label="P90" value={niche.p90} max={niche.p90} />
                  </div>
                  <div className="mt-3 pt-3 border-t border-slate-700 flex items-center justify-between text-xs text-slate-500">
                    <span>{niche.sample_size.toLocaleString()} samples</span>
                    <span>Reach threshold: {niche.outlier_reach_threshold}×</span>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function GhostStat({
  icon,
  label,
  value,
  bg,
}: {
  icon: ReactNode
  label: string
  value: number
  bg: string
}) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 flex items-center gap-4">
      <div className={`rounded-xl p-3 ${bg}`}>{icon}</div>
      <div>
        <p className="text-sm text-slate-400">{label}</p>
        <p className="text-2xl font-bold text-slate-100 mt-0.5">{value.toLocaleString()}</p>
      </div>
    </div>
  )
}

function PercentileBar({
  label,
  value,
  max,
}: {
  label: string
  value: number | null
  max: number | null
}) {
  if (value == null || max == null || max === 0) return null
  const pct = Math.min(100, (value / max) * 100)
  return (
    <div className="flex items-center gap-2">
      <span className="w-6 text-slate-500 text-xs">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-slate-700">
        <div
          className="h-full rounded-full bg-pink-500/60"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-14 text-right text-slate-400 font-mono">
        {value >= 1_000_000
          ? `${(value / 1_000_000).toFixed(1)}M`
          : value >= 1_000
          ? `${(value / 1_000).toFixed(0)}K`
          : value.toFixed(0)}
      </span>
    </div>
  )
}
