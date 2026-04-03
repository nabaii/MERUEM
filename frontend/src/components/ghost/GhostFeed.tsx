import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, Eye, Heart, Zap } from 'lucide-react'
import type { GhostViralPost } from '../../api/ghostVirality'
import { Badge } from '../ui/Badge'
import { timeAgo, formatNumber } from '../../lib/utils'

const STRATEGY_CONFIG: Record<string, { label: string; color: 'pink' | 'cyan' | 'yellow' | 'purple' | 'green' | 'gray' }> = {
  high_dm_share:       { label: 'High DM Share', color: 'pink' },
  watch_time_arbitrage:{ label: 'Watch Time Arb', color: 'cyan' },
  audio_driven:        { label: 'Audio-Driven', color: 'purple' },
  polarizing:          { label: 'Polarizing', color: 'yellow' },
  utility:             { label: 'Utility', color: 'green' },
  unknown:             { label: 'Unclassified', color: 'gray' },
}

interface Props {
  posts: GhostViralPost[]
  loading?: boolean
}

type SortKey = 'ghost_virality_delta' | 'outlier_reach_ratio' | 'view_count' | 'detected_at'

export function GhostFeed({ posts, loading }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('ghost_virality_delta')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(d => (d === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sorted = [...posts].sort((a, b) => {
    const av = a[sortKey] ?? 0
    const bv = b[sortKey] ?? 0
    const cmp = typeof av === 'string'
      ? (av as string).localeCompare(bv as string)
      : (av as number) - (bv as number)
    return sortDir === 'desc' ? -cmp : cmp
  })

  function SortHeader({ label, k }: { label: string; k: SortKey }) {
    const active = sortKey === k
    return (
      <th
        className="pb-2 font-medium cursor-pointer select-none hover:text-slate-300 transition-colors"
        onClick={() => toggleSort(k)}
      >
        <span className="flex items-center gap-1">
          {label}
          {active && <span className="text-brand-400">{sortDir === 'desc' ? '↓' : '↑'}</span>}
        </span>
      </th>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-500 text-sm">
        Loading ghost feed…
      </div>
    )
  }

  if (posts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="mb-4 rounded-2xl bg-slate-700/40 p-5">
          <Zap size={28} className="text-pink-400" />
        </div>
        <p className="text-slate-400 text-sm">No ghost viral posts detected yet.</p>
        <p className="text-slate-500 text-xs mt-1">Start a scout job to begin collecting data.</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 text-left text-xs text-slate-500">
            <th className="pb-2 font-medium">Account</th>
            <th className="pb-2 font-medium">Niche</th>
            <SortHeader label="GV Delta" k="ghost_virality_delta" />
            <SortHeader label="Reach Ratio" k="outlier_reach_ratio" />
            <SortHeader label="Views" k="view_count" />
            <th className="pb-2 font-medium">Likes</th>
            <th className="pb-2 font-medium">Strategy</th>
            <th className="pb-2 font-medium">Pattern</th>
            <SortHeader label="Detected" k="detected_at" />
            <th className="pb-2 font-medium">Link</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/50">
          {sorted.map(post => {
            const strategy = STRATEGY_CONFIG[post.strategy_label ?? 'unknown'] ?? STRATEGY_CONFIG.unknown
            return (
              <tr key={post.id} className="hover:bg-slate-700/20 transition-colors group">
                <td className="py-3 pr-4">
                  <Link
                    to={`/ghost-virality/${post.id}`}
                    className="font-medium text-slate-200 hover:text-brand-400 transition-colors"
                  >
                    @{post.account_username}
                  </Link>
                </td>
                <td className="py-3 pr-4">
                  {post.niche ? (
                    <span className="text-slate-400 text-xs">{post.niche}</span>
                  ) : (
                    <span className="text-slate-600 text-xs">—</span>
                  )}
                </td>
                <td className="py-3 pr-4">
                  <span className="font-mono text-pink-300 font-semibold">
                    {post.ghost_virality_delta != null
                      ? post.ghost_virality_delta >= 9999
                        ? '∞'
                        : post.ghost_virality_delta.toFixed(0)
                      : '—'}
                    ×
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <span className="font-mono text-cyan-300 text-xs">
                    {post.outlier_reach_ratio != null
                      ? `${post.outlier_reach_ratio.toFixed(1)}×`
                      : '—'}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <span className="flex items-center gap-1 text-slate-300">
                    <Eye size={12} className="text-slate-500" />
                    {post.view_count != null ? formatNumber(post.view_count) : '—'}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <span className="flex items-center gap-1 text-slate-400 text-xs">
                    <Heart size={12} className="text-slate-600" />
                    {post.like_count != null ? formatNumber(post.like_count) : '—'}
                  </span>
                </td>
                <td className="py-3 pr-4">
                  <Badge color={strategy.color}>{strategy.label}</Badge>
                </td>
                <td className="py-3 pr-4">
                  {post.pattern_card_ready ? (
                    <Badge color="green">Ready</Badge>
                  ) : (
                    <Badge color="gray">Pending</Badge>
                  )}
                </td>
                <td className="py-3 pr-4 text-slate-500 text-xs whitespace-nowrap">
                  {timeAgo(post.detected_at)}
                </td>
                <td className="py-3">
                  {post.permalink ? (
                    <a
                      href={post.permalink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-slate-500 hover:text-brand-400 transition-colors"
                    >
                      <ExternalLink size={14} />
                    </a>
                  ) : (
                    <span className="text-slate-700">—</span>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
