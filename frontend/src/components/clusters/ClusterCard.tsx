import { Link } from 'react-router-dom'
import { Users } from 'lucide-react'
import type { Cluster } from '../../api/clusters'
import { formatNumber, TOPIC_COLORS } from '../../lib/utils'

export function ClusterCard({ cluster }: { cluster: Cluster }) {
  const topTopics = cluster.top_interests
    ? Object.entries(cluster.top_interests)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([t]) => t)
    : []

  return (
    <Link
      to={`/clusters/${cluster.id}`}
      className="block bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-brand-600/60 transition-colors"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">
            {cluster.label ?? `Cluster ${cluster.id}`}
          </h3>
          <p className="flex items-center gap-1.5 mt-1 text-xs text-slate-500">
            <Users size={12} />
            {formatNumber(cluster.member_count)} members
          </p>
        </div>
        <span className="text-2xl font-bold text-slate-700">#{cluster.id}</span>
      </div>

      {topTopics.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {topTopics.map((t) => (
            <span
              key={t}
              className="inline-block px-2 py-0.5 rounded-md text-xs font-medium"
              style={{
                backgroundColor: `${TOPIC_COLORS[t] ?? '#3b82f6'}22`,
                color: TOPIC_COLORS[t] ?? '#3b82f6',
              }}
            >
              {t}
            </span>
          ))}
        </div>
      )}
    </Link>
  )
}
