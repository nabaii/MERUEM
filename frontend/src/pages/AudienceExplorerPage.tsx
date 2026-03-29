import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { profilesApi, type ProfileFilters } from '../api/profiles'
import { ProfileCard } from '../components/profiles/ProfileCard'
import { AudienceFilters } from '../components/filters/AudienceFilters'
import { PageSpinner } from '../components/ui/Spinner'
import { Button } from '../components/ui/Button'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const DEFAULT_FILTERS: ProfileFilters = { limit: 24, offset: 0 }

export function AudienceExplorerPage() {
  const [filters, setFilters] = useState<ProfileFilters>(DEFAULT_FILTERS)

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['profiles', filters],
    queryFn: () => profilesApi.list(filters),
    placeholderData: (prev) => prev,
  })

  const total = data?.total ?? 0
  const page = Math.floor((filters.offset ?? 0) / (filters.limit ?? 24)) + 1
  const totalPages = Math.ceil(total / (filters.limit ?? 24))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Audience Explorer</h1>
        <p className="text-sm text-slate-400 mt-1">Search and filter across all collected profiles</p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar filters */}
        <div className="w-64 flex-shrink-0">
          <AudienceFilters
            filters={filters}
            onChange={setFilters}
            onReset={() => setFilters(DEFAULT_FILTERS)}
          />
        </div>

        {/* Results */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-slate-400">
              {isFetching ? 'Loading…' : `${total.toLocaleString()} profiles`}
            </p>
            {totalPages > 1 && (
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <span>Page {page} of {totalPages}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={(filters.offset ?? 0) === 0}
                  onClick={() => setFilters((f) => ({ ...f, offset: (f.offset ?? 0) - (f.limit ?? 24) }))}
                >
                  <ChevronLeft size={15} />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setFilters((f) => ({ ...f, offset: (f.offset ?? 0) + (f.limit ?? 24) }))}
                >
                  <ChevronRight size={15} />
                </Button>
              </div>
            )}
          </div>

          {isLoading ? (
            <PageSpinner />
          ) : data?.items.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-500">
              <p className="text-lg">No profiles found</p>
              <p className="text-sm mt-1">Try adjusting your filters</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {data?.items.map((p) => <ProfileCard key={p.id} profile={p} />)}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
