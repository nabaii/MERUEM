import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Megaphone } from 'lucide-react'
import toast from 'react-hot-toast'
import { campaignsApi, CampaignStatus } from '../api/campaigns'
import { CampaignCard } from '../components/campaigns/CampaignCard'
import { Spinner } from '../components/ui/Spinner'

const TABS: { label: string; value: CampaignStatus | undefined }[] = [
  { label: 'All', value: undefined },
  { label: 'Draft', value: 'draft' },
  { label: 'Active', value: 'active' },
  { label: 'Exported', value: 'exported' },
  { label: 'Completed', value: 'completed' },
]

export function CampaignsPage() {
  const qc = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<CampaignStatus | undefined>()
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')

  const { data: campaigns, isLoading } = useQuery({
    queryKey: ['campaigns', statusFilter],
    queryFn: () => campaignsApi.list(statusFilter),
  })

  const createMutation = useMutation({
    mutationFn: () => campaignsApi.create({ name: newName.trim() }),
    onSuccess: () => {
      toast.success('Campaign created')
      qc.invalidateQueries({ queryKey: ['campaigns'] })
      setShowNew(false)
      setNewName('')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="flex-1 p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Campaigns</h1>
          <p className="text-sm text-slate-400 mt-0.5">Build and export audience lists</p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus size={15} />
          New Campaign
        </button>
      </div>

      {/* New campaign inline form */}
      {showNew && (
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4 flex items-center gap-3">
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && newName.trim()) createMutation.mutate()
              if (e.key === 'Escape') { setShowNew(false); setNewName('') }
            }}
            placeholder="Campaign name…"
            className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <button
            disabled={!newName.trim() || createMutation.isPending}
            onClick={() => createMutation.mutate()}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Create
          </button>
          <button
            onClick={() => { setShowNew(false); setNewName('') }}
            className="px-3 py-2 text-slate-400 hover:text-slate-100 text-sm rounded-lg"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Status tabs */}
      <div className="flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.label}
            onClick={() => setStatusFilter(t.value)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              statusFilter === t.value
                ? 'bg-brand-600/20 text-brand-400'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Campaign grid */}
      {isLoading ? (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      ) : campaigns && campaigns.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {campaigns.map((c) => (
            <CampaignCard key={c.id} campaign={c} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 text-slate-500">
          <Megaphone size={40} className="mb-3 opacity-30" />
          <p className="text-sm">No campaigns yet. Create one to get started.</p>
        </div>
      )}
    </div>
  )
}
