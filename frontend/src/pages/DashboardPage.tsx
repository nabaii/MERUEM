import { useQuery } from '@tanstack/react-query'
import { Users, FileText, Network, Loader, AlertTriangle } from 'lucide-react'

import { statsApi } from '../api/stats'
import { StatCard } from '../components/dashboard/StatCard'
import { ClusterBubbleChart } from '../components/dashboard/ClusterBubbleChart'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { PageSpinner } from '../components/ui/Spinner'
import { timeAgo } from '../lib/utils'

const STATUS_COLOR: Record<string, 'green' | 'blue' | 'red' | 'gray'> = {
  completed: 'green',
  running: 'blue',
  failed: 'red',
  pending: 'gray',
}

export function DashboardPage() {
  const { data, error, isError, isLoading, isRefetching, refetch } = useQuery({
    queryKey: ['stats'],
    queryFn: statsApi.get,
    refetchInterval: 30_000,
  })

  if (isLoading) return <PageSpinner />

  if (isError || !data) {
    return (
      <Card className="border-red-900/60 bg-red-950/20">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-red-900/40 p-3">
              <AlertTriangle size={20} className="text-red-300" />
            </div>
            <div className="space-y-2">
              <div>
                <h1 className="text-xl font-semibold text-slate-100">Dashboard unavailable</h1>
                <p className="mt-1 text-sm text-slate-300">
                  {error instanceof Error
                    ? error.message
                    : 'We could not load the dashboard data right now.'}
                </p>
              </div>
              <p className="text-sm text-slate-400">
                If you are running locally, start the backend API and try again.
              </p>
            </div>
          </div>
          <Button variant="secondary" onClick={() => refetch()} loading={isRefetching}>
            Retry
          </Button>
        </div>
      </Card>
    )
  }

  const stats = {
    ...data,
    profiles_by_platform: data.profiles_by_platform ?? [],
    top_clusters: data.top_clusters ?? [],
    recent_jobs: data.recent_jobs ?? [],
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-400">Platform overview</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total Profiles" value={stats.total_profiles} icon={Users} color="blue" />
        <StatCard label="Total Posts" value={stats.total_posts} icon={FileText} color="green" />
        <StatCard label="Audience Clusters" value={stats.total_clusters} icon={Network} color="purple" />
        <StatCard label="Active Jobs" value={stats.active_jobs} icon={Loader} color="yellow" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Audience Clusters</CardTitle>
          </CardHeader>
          {stats.top_clusters.length > 0 ? (
            <ClusterBubbleChart
              clusters={stats.top_clusters.map((cluster) => ({
                id: cluster.id,
                label: cluster.label,
                description: null,
                member_count: cluster.member_count,
                top_interests: null,
                last_updated: '',
              }))}
            />
          ) : (
            <p className="py-8 text-center text-sm text-slate-500">
              No clusters yet — run the intelligence pipeline to generate them.
            </p>
          )}
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Profiles by platform</CardTitle>
          </CardHeader>
          <ul className="space-y-3">
            {stats.profiles_by_platform.length > 0 ? (
              stats.profiles_by_platform.map((platform) => (
                <li key={platform.platform} className="flex items-center justify-between">
                  <span className="text-sm capitalize text-slate-300">{platform.platform}</span>
                  <Badge color="blue">{platform.count.toLocaleString()}</Badge>
                </li>
              ))
            ) : (
              <p className="text-sm text-slate-500">No data yet.</p>
            )}
          </ul>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent collection jobs</CardTitle>
        </CardHeader>
        {stats.recent_jobs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-left text-xs text-slate-500">
                  <th className="pb-2 font-medium">Platform</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Profiles</th>
                  <th className="pb-2 font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {stats.recent_jobs.map((job) => (
                  <tr key={job.id}>
                    <td className="py-2.5 capitalize text-slate-200">{job.platform}</td>
                    <td className="py-2.5">
                      <Badge color={STATUS_COLOR[job.status] ?? 'gray'}>{job.status}</Badge>
                    </td>
                    <td className="py-2.5 text-slate-300">
                      {job.profiles_collected.toLocaleString()}
                    </td>
                    <td className="py-2.5 text-slate-500">{timeAgo(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-slate-500">No jobs run yet.</p>
        )}
      </Card>
    </div>
  )
}
