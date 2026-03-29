import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { clustersApi } from '../api/clusters'
import { ProfileCard } from '../components/profiles/ProfileCard'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { PageSpinner } from '../components/ui/Spinner'
import { formatNumber, TOPIC_COLORS } from '../lib/utils'
import { ArrowLeft, Users } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export function ClusterDetailPage() {
  const { id } = useParams<{ id: string }>()
  const clusterId = Number(id)

  const { data: cluster, isLoading: loadingCluster } = useQuery({
    queryKey: ['cluster', clusterId],
    queryFn: () => clustersApi.get(clusterId),
    enabled: !!clusterId,
  })

  const { data: profilesData, isLoading: loadingProfiles } = useQuery({
    queryKey: ['cluster-profiles', clusterId],
    queryFn: () => clustersApi.profiles(clusterId, 12, 0),
    enabled: !!clusterId,
  })

  if (loadingCluster) return <PageSpinner />
  if (!cluster) return <p className="text-slate-400">Cluster not found.</p>

  const interestData = cluster.top_interests
    ? Object.entries(cluster.top_interests)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 8)
        .map(([topic, count]) => ({ topic, count }))
    : []

  return (
    <div className="space-y-6 max-w-6xl">
      <Link to="/clusters" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={15} /> All clusters
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">
            {cluster.label ?? `Cluster ${cluster.id}`}
          </h1>
          <p className="flex items-center gap-1.5 mt-1 text-sm text-slate-400">
            <Users size={14} /> {formatNumber(cluster.member_count)} members
          </p>
        </div>
        <span className="text-4xl font-bold text-slate-800">#{cluster.id}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Interest distribution bar chart */}
        <Card>
          <CardHeader><CardTitle>Interest distribution</CardTitle></CardHeader>
          {interestData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={interestData} layout="vertical">
                <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis
                  dataKey="topic"
                  type="category"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  width={80}
                />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                  cursor={{ fill: '#ffffff08' }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {interestData.map((entry) => (
                    <Cell
                      key={entry.topic}
                      fill={TOPIC_COLORS[entry.topic] ?? '#3b82f6'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-slate-500">No interest data.</p>
          )}
        </Card>

        {/* Top topics summary */}
        <Card>
          <CardHeader><CardTitle>Top interests</CardTitle></CardHeader>
          {interestData.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {interestData.map(({ topic }) => (
                <span
                  key={topic}
                  className="inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-medium capitalize"
                  style={{
                    backgroundColor: `${TOPIC_COLORS[topic] ?? '#3b82f6'}20`,
                    color: TOPIC_COLORS[topic] ?? '#3b82f6',
                  }}
                >
                  {topic}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">No interests classified yet.</p>
          )}
        </Card>
      </div>

      {/* Member profiles */}
      <div>
        <h2 className="text-base font-semibold text-slate-100 mb-4">
          Representative members
          {profilesData && (
            <span className="text-slate-500 font-normal ml-2 text-sm">
              (showing {profilesData.items.length} of {profilesData.total})
            </span>
          )}
        </h2>
        {loadingProfiles ? (
          <PageSpinner />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {profilesData?.items.map((p) => <ProfileCard key={p.id} profile={p} />)}
          </div>
        )}
      </div>
    </div>
  )
}
