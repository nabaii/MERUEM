import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Zap, TrendingUp, CheckCircle2, ArrowRight, Eye, Heart } from 'lucide-react'
import { ghostViralityApi } from '../../api/ghostVirality'
import { Badge } from '../ui/Badge'
import { Card, CardHeader, CardTitle } from '../ui/Card'
import { Button } from '../ui/Button'
import { formatNumber, timeAgo } from '../../lib/utils'

const STRATEGY_COLOR: Record<string, 'pink' | 'cyan' | 'yellow' | 'purple' | 'green' | 'gray'> = {
  high_dm_share: 'pink',
  watch_time_arbitrage: 'cyan',
  audio_driven: 'purple',
  polarizing: 'yellow',
  utility: 'green',
  unknown: 'gray',
}

const STRATEGY_LABEL: Record<string, string> = {
  high_dm_share: 'High DM Share',
  watch_time_arbitrage: 'Watch Time Arb',
  audio_driven: 'Audio-Driven',
  polarizing: 'Polarizing',
  utility: 'Utility',
  unknown: 'Unknown',
}

export function InstagramDashboardTab() {
  const { data: stats } = useQuery({
    queryKey: ['ghost-stats'],
    queryFn: ghostViralityApi.getStats,
    refetchInterval: 30_000,
  })

  const { data: recentPosts = [], isLoading } = useQuery({
    queryKey: ['ghost-feed-recent'],
    queryFn: () => ghostViralityApi.listGhosts({ days: 7, limit: 5 }),
    refetchInterval: 60_000,
  })

  return (
    <div className="space-y-6">
      {/* Ghost Virality intro banner */}
      <Card className="border-pink-500/20 bg-gradient-to-br from-pink-950/20 to-slate-800">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-pink-900/40 p-3 shrink-0">
              <Zap size={22} className="text-pink-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-100">Ghost Virality Pipeline</h2>
              <p className="text-sm text-slate-400 mt-0.5">
                Detects Reels the algorithm is aggressively distributing despite low engagement —
                your arbitrage opportunity driven by watch time and DM shares.
              </p>
            </div>
          </div>
          <Link to="/ghost-virality">
            <Button size="sm">
              Open Pipeline
              <ArrowRight size={13} />
            </Button>
          </Link>
        </div>
      </Card>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <StatTile icon={<Zap size={14} className="text-pink-400" />} label="Ghost Posts" value={stats.total_ghost_posts} />
          <StatTile icon={<TrendingUp size={14} className="text-yellow-400" />} label="New (7d)" value={stats.new_last_7_days} />
          <StatTile icon={<Eye size={14} className="text-blue-400" />} label="Pattern Cards" value={stats.pattern_cards_ready} />
          <StatTile icon={<TrendingUp size={14} className="text-cyan-400" />} label="Trial Reels" value={stats.trial_reels_total} />
          <StatTile icon={<CheckCircle2 size={14} className="text-emerald-400" />} label="Green Lit" value={stats.trial_reels_green_lit} />
          <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-4">
            <p className="text-xs text-slate-500 mb-2">Top niche</p>
            {stats.top_niches[0] ? (
              <>
                <p className="font-semibold text-slate-200 capitalize">{stats.top_niches[0].niche}</p>
                <p className="text-xs text-slate-500">{stats.top_niches[0].count} posts</p>
              </>
            ) : (
              <p className="text-xs text-slate-600">No data yet</p>
            )}
          </div>
        </div>
      )}

      {/* Recent ghost posts */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Recent Ghost Viral Posts</CardTitle>
            <Link to="/ghost-virality">
              <Button variant="secondary" size="sm">
                View all
                <ArrowRight size={12} />
              </Button>
            </Link>
          </div>
        </CardHeader>

        {isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : recentPosts.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-slate-500 text-sm">No ghost viral posts detected yet.</p>
            <Link to="/ghost-virality">
              <Button size="sm" className="mt-3">
                Start a scout job
              </Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {recentPosts.map(post => (
              <Link
                key={post.id}
                to={`/ghost-virality/${post.id}`}
                className="flex items-center justify-between rounded-lg border border-slate-700/50 bg-slate-700/20 px-4 py-3 hover:bg-slate-700/40 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="rounded-lg bg-pink-900/30 p-1.5 shrink-0">
                    <Zap size={13} className="text-pink-400" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-200 truncate">
                      @{post.account_username}
                    </p>
                    <p className="text-xs text-slate-500">
                      {post.niche ?? 'Unknown niche'} · {timeAgo(post.detected_at)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <div className="hidden sm:flex items-center gap-3 text-xs text-slate-400">
                    <span className="flex items-center gap-1">
                      <Eye size={11} />
                      {post.view_count != null ? formatNumber(post.view_count) : '—'}
                    </span>
                    <span className="flex items-center gap-1">
                      <Heart size={11} />
                      {post.like_count != null ? formatNumber(post.like_count) : '—'}
                    </span>
                    <span className="font-mono text-pink-300 font-semibold">
                      {post.ghost_virality_delta != null
                        ? `${post.ghost_virality_delta >= 9999 ? '∞' : post.ghost_virality_delta.toFixed(0)}×`
                        : '—'}
                    </span>
                  </div>
                  {post.strategy_label && (
                    <Badge color={STRATEGY_COLOR[post.strategy_label] ?? 'gray'}>
                      {STRATEGY_LABEL[post.strategy_label] ?? post.strategy_label}
                    </Badge>
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function StatTile({
  icon,
  label,
  value,
}: {
  icon: ReactNode
  label: string
  value: number
}) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-4">
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-xs text-slate-500">{label}</span>
      </div>
      <p className="text-2xl font-bold text-slate-100">{value.toLocaleString()}</p>
    </div>
  )
}
