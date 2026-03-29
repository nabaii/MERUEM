import { useQuery } from '@tanstack/react-query'
import { clustersApi } from '../api/clusters'
import { ClusterCard } from '../components/clusters/ClusterCard'
import { PageSpinner } from '../components/ui/Spinner'
import { Network } from 'lucide-react'

export function ClustersPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['clusters'],
    queryFn: () => clustersApi.list(),
  })

  if (isLoading) return <PageSpinner />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Audience Clusters</h1>
        <p className="text-sm text-slate-400 mt-1">
          {data?.total ?? 0} segments auto-discovered by the ML pipeline
        </p>
      </div>

      {data?.items.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-slate-500 gap-3">
          <Network size={40} className="text-slate-700" />
          <p className="text-lg">No clusters yet</p>
          <p className="text-sm">Run the nightly intelligence pipeline to generate audience segments.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {data?.items.map((c) => <ClusterCard key={c.id} cluster={c} />)}
        </div>
      )}
    </div>
  )
}
