import { useQuery } from '@tanstack/react-query'
import { Search, Users, FileText, Clock, FlaskConical } from 'lucide-react'

import { discoveryApi } from '../../api/discovery'
import { statsApi } from '../../api/stats'
import { TwitterDiscoveryPanel } from './TwitterDiscoveryPanel'
import { StatCard } from '../dashboard/StatCard'
import { Card, CardHeader, CardTitle } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { timeAgo } from '../../lib/utils'

const STATUS_COLOR: Record<string, 'green' | 'blue' | 'red' | 'gray'> = {
  completed: 'green',
  searching: 'blue',
  expanding: 'blue',
  failed: 'red',
  pending: 'gray',
}

export function TwitterDashboardTab() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: statsApi.get,
    refetchInterval: 30_000,
  })

  const { data: history } = useQuery({
    queryKey: ['discovery-history'],
    queryFn: discoveryApi.getHistory,
    refetchInterval: 15_000,
  })

  // Filter platform-specific stats
  const twitterProfiles =
    stats?.profiles_by_platform?.find((p: { platform: string }) => p.platform === 'twitter')?.count ?? 0
  const dummyRuns = history?.jobs?.filter((job) => job.dummy_mode).length ?? 0

  return (
    <div className="space-y-8">
      <Card className="border-amber-500/20 bg-gradient-to-r from-amber-500/10 to-slate-900">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-2xl bg-amber-500/15 p-3">
              <FlaskConical size={20} className="text-amber-300" />
            </div>
            <div>
              <CardTitle className="text-base text-slate-100">Simulation Mode Ready</CardTitle>
              <p className="mt-1 text-sm text-slate-300">
                Open User Discovery and toggle Dummy Mode to run a full Twitter search simulation with sample users, enrichment fields, export, print, and shared-followings analysis.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge color="yellow">{dummyRuns} dummy runs</Badge>
            <Badge color="blue">{history?.jobs?.length ?? 0} total runs</Badge>
          </div>
        </div>
      </Card>

      {/* Twitter-specific KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Twitter Profiles"
          value={twitterProfiles}
          icon={Users}
          color="blue"
        />
        <StatCard
          label="Discovery Runs"
          value={history?.jobs?.length ?? 0}
          icon={Search}
          color="green"
        />
        <StatCard
          label="Total Tweets Scanned"
          value={
            history?.jobs?.reduce((sum, j) => sum + (j.tweets_scanned || 0), 0) ?? 0
          }
          icon={FileText}
          color="purple"
        />
        <StatCard
          label="Location Matches"
          value={
            history?.jobs?.reduce((sum, j) => sum + (j.location_matched || 0), 0) ?? 0
          }
          icon={Clock}
          color="yellow"
        />
      </div>

      {/* Main Discovery Panel */}
      <TwitterDiscoveryPanel />

      {/* Discovery History */}
      {history && history.jobs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock size={18} className="text-slate-400" />
              Recent Discovery Runs
            </CardTitle>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" id="discovery-history-table">
              <thead>
                <tr className="text-left text-xs text-slate-500 border-b border-slate-700">
                  <th className="pb-2 font-medium">Keywords</th>
                  <th className="pb-2 font-medium">Mode</th>
                  <th className="pb-2 font-medium">Location</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium text-right">Users</th>
                  <th className="pb-2 font-medium text-right">Tweets</th>
                  <th className="pb-2 font-medium text-right">Matches</th>
                  <th className="pb-2 font-medium">When</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                {history.jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-700/20 transition-colors">
                    <td className="py-2.5">
                      <div className="flex flex-wrap gap-1 max-w-xs">
                        {job.seed_keywords.slice(0, 3).map((kw, i) => (
                          <Badge key={i} color="blue">{kw}</Badge>
                        ))}
                        {job.seed_keywords.length > 3 && (
                          <Badge color="gray">+{job.seed_keywords.length - 3}</Badge>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5">
                      <Badge color={job.dummy_mode ? 'yellow' : 'gray'}>
                        {job.dummy_mode ? 'Dummy' : 'Live'}
                      </Badge>
                    </td>
                    <td className="py-2.5 text-slate-300">{job.location}</td>
                    <td className="py-2.5">
                      <Badge color={STATUS_COLOR[job.status] ?? 'gray'}>
                        {job.status}
                      </Badge>
                    </td>
                    <td className="py-2.5 text-right text-slate-300">
                      {job.results_count}
                    </td>
                    <td className="py-2.5 text-right text-slate-300">
                      {job.tweets_scanned}
                    </td>
                    <td className="py-2.5 text-right text-emerald-400">
                      {job.location_matched}
                    </td>
                    <td className="py-2.5 text-slate-500">{timeAgo(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
