import type { ReactNode } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, RefreshCw, Eye, Heart, Users, TrendingUp, Zap } from 'lucide-react'
import toast from 'react-hot-toast'
import { ghostViralityApi } from '../api/ghostVirality'
import { PatternCard } from '../components/ghost/PatternCard'
import { TrialReelTracker } from '../components/ghost/TrialReelTracker'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { PageSpinner } from '../components/ui/Spinner'
import { formatNumber, timeAgo } from '../lib/utils'

const STRATEGY_LABELS: Record<string, string> = {
  high_dm_share: 'High DM Share',
  watch_time_arbitrage: 'Watch Time Arb',
  audio_driven: 'Audio-Driven',
  polarizing: 'Polarizing',
  utility: 'Utility',
  unknown: 'Unclassified',
}

export function GhostPostDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()

  const { data: post, isLoading, isError } = useQuery({
    queryKey: ['ghost-post', id],
    queryFn: () => ghostViralityApi.getGhost(id!),
    enabled: !!id,
  })

  const retryMut = useMutation({
    mutationFn: () => ghostViralityApi.retryPatternRecognition(id!),
    onSuccess: () => {
      toast.success('Pattern recognition re-queued')
      qc.invalidateQueries({ queryKey: ['ghost-post', id] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  if (isLoading) return <PageSpinner />
  if (isError || !post) {
    return (
      <Card className="border-red-900/60">
        <p className="text-red-300">Ghost Viral post not found.</p>
        <Link to="/ghost-virality" className="text-sm text-brand-400 hover:underline mt-2 inline-block">
          ← Back to Ghost Virality
        </Link>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2">
        <Link
          to="/ghost-virality"
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft size={14} />
          Ghost Virality
        </Link>
        <span className="text-slate-600">/</span>
        <span className="text-sm text-slate-300">@{post.account_username}</span>
      </div>

      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold text-slate-100">@{post.account_username}</h1>
            {post.niche && <Badge color="gray">{post.niche}</Badge>}
            {post.strategy_label && (
              <Badge color="pink">{STRATEGY_LABELS[post.strategy_label] ?? post.strategy_label}</Badge>
            )}
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Detected {timeAgo(post.detected_at)}
            {post.posted_at && ` · Posted ${timeAgo(post.posted_at)}`}
          </p>
        </div>
        <div className="flex gap-2">
          {post.permalink && (
            <a href={post.permalink} target="_blank" rel="noopener noreferrer">
              <Button variant="secondary" size="sm">
                <ExternalLink size={13} />
                View on Instagram
              </Button>
            </a>
          )}
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <MetricBox
          icon={<Zap size={14} className="text-pink-400" />}
          label="GV Delta"
          value={
            post.ghost_virality_delta != null
              ? post.ghost_virality_delta >= 9999
                ? '∞'
                : `${post.ghost_virality_delta.toFixed(0)}×`
              : '—'
          }
          highlight
        />
        <MetricBox
          icon={<TrendingUp size={14} className="text-cyan-400" />}
          label="Reach Ratio"
          value={post.outlier_reach_ratio != null ? `${post.outlier_reach_ratio.toFixed(1)}×` : '—'}
        />
        <MetricBox
          icon={<Eye size={14} className="text-blue-400" />}
          label="Views"
          value={post.view_count != null ? formatNumber(post.view_count) : '—'}
        />
        <MetricBox
          icon={<Heart size={14} className="text-red-400" />}
          label="Likes"
          value={post.like_count != null ? formatNumber(post.like_count) : '—'}
        />
        <MetricBox
          icon={<Users size={14} className="text-slate-400" />}
          label="Followers"
          value={post.follower_count != null ? formatNumber(post.follower_count) : '—'}
        />
      </div>

      {/* Velocity */}
      {(post.view_velocity != null || post.like_velocity != null) && (
        <Card className="border-slate-600">
          <CardHeader>
            <CardTitle>Engagement Velocity</CardTitle>
          </CardHeader>
          <div className="flex gap-8">
            {post.view_velocity != null && (
              <div>
                <p className="text-xl font-bold text-slate-100">
                  +{formatNumber(Math.round(post.view_velocity))}/hr
                </p>
                <p className="text-xs text-slate-500">View rate</p>
              </div>
            )}
            {post.like_velocity != null && (
              <div>
                <p className={`text-xl font-bold ${post.like_velocity <= 0 ? 'text-emerald-400' : 'text-slate-100'}`}>
                  {post.like_velocity > 0 ? '+' : ''}{formatNumber(Math.round(post.like_velocity))}/hr
                </p>
                <p className="text-xs text-slate-500">Like rate</p>
                {post.like_velocity <= 0 && (
                  <p className="text-xs text-emerald-400 mt-0.5">Strong ghost viral signal</p>
                )}
              </div>
            )}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Pattern Card */}
        <div className="space-y-3">
          {post.pattern_card ? (
            <PatternCard card={post.pattern_card} />
          ) : (
            <Card className="border-slate-700">
              <CardHeader>
                <CardTitle>Pattern Card</CardTitle>
              </CardHeader>
              <div className="flex flex-col items-center py-6 text-center">
                <p className="text-slate-400 text-sm mb-3">
                  {post.pattern_card_ready
                    ? 'Pattern card was generated but could not be loaded.'
                    : 'Pattern recognition is queued and will run shortly.'}
                </p>
                <Button
                  variant="secondary"
                  size="sm"
                  loading={retryMut.isPending}
                  onClick={() => retryMut.mutate()}
                >
                  <RefreshCw size={13} />
                  Re-run pattern recognition
                </Button>
              </div>
            </Card>
          )}
        </div>

        {/* Trial Reels */}
        <TrialReelTracker ghostPostId={post.id} niche={post.niche ?? undefined} />
      </div>
    </div>
  )
}

function MetricBox({
  icon,
  label,
  value,
  highlight,
}: {
  icon: ReactNode
  label: string
  value: string
  highlight?: boolean
}) {
  return (
    <Card className={`text-center ${highlight ? 'border-pink-500/30 bg-pink-950/10' : ''}`}>
      <div className="flex items-center justify-center gap-1.5 mb-1">
        {icon}
        <span className="text-xs text-slate-500">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${highlight ? 'text-pink-300' : 'text-slate-100'}`}>
        {value}
      </p>
    </Card>
  )
}
