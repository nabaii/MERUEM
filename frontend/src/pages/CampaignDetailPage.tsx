import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Download, Play, Trash2, RefreshCw, Users, FileDown } from 'lucide-react'
import toast from 'react-hot-toast'
import { campaignsApi, ExportFormat } from '../api/campaigns'
import { Spinner } from '../components/ui/Spinner'
import { cn } from '../lib/utils'

const FORMAT_LABELS: Record<ExportFormat, string> = {
  meta: 'Meta Custom Audience',
  twitter: 'Twitter/X Tailored Audience',
  csv: 'Generic CSV',
}

const STATUS_STYLE: Record<string, string> = {
  pending: 'text-yellow-400',
  processing: 'text-blue-400',
  ready: 'text-green-400',
  failed: 'text-red-400',
}

export function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('csv')

  const { data: campaign, isLoading } = useQuery({
    queryKey: ['campaign', id],
    queryFn: () => campaignsApi.get(id!),
    refetchInterval: 10_000, // poll while exports process
  })

  const activateMutation = useMutation({
    mutationFn: () => campaignsApi.activate(id!),
    onSuccess: () => {
      toast.success('Campaign activated')
      qc.invalidateQueries({ queryKey: ['campaign', id] })
      qc.invalidateQueries({ queryKey: ['campaigns'] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const exportMutation = useMutation({
    mutationFn: () => campaignsApi.createExport(id!, selectedFormat),
    onSuccess: () => {
      toast.success('Export queued — check back shortly')
      qc.invalidateQueries({ queryKey: ['campaign', id] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const deleteMutation = useMutation({
    mutationFn: () => campaignsApi.delete(id!),
    onSuccess: () => {
      toast.success('Campaign deleted')
      navigate('/campaigns')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  if (isLoading || !campaign) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    )
  }

  const isDraft = campaign.status === 'draft'
  const canExport = campaign.status !== 'draft'

  return (
    <div className="flex-1 p-6 space-y-6 max-w-4xl">
      {/* Back + Header */}
      <div>
        <button
          onClick={() => navigate('/campaigns')}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-100 mb-4"
        >
          <ArrowLeft size={14} />
          Campaigns
        </button>

        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">{campaign.name}</h1>
            <div className="flex items-center gap-3 mt-1 text-sm text-slate-400">
              <span className="capitalize">{campaign.status}</span>
              <span>·</span>
              <span className="flex items-center gap-1">
                <Users size={13} />
                {campaign.audience_count.toLocaleString()} profiles
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isDraft && (
              <button
                onClick={() => activateMutation.mutate()}
                disabled={activateMutation.isPending || campaign.audience_count === 0}
                className="flex items-center gap-2 px-4 py-2 bg-green-700 hover:bg-green-600 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
              >
                <Play size={14} />
                Activate
              </button>
            )}
            <button
              onClick={() => {
                if (confirm('Delete this campaign?')) deleteMutation.mutate()
              }}
              className="flex items-center gap-2 px-3 py-2 bg-red-900/40 hover:bg-red-800/60 text-red-400 text-sm rounded-lg transition-colors"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Filters summary */}
      {campaign.filters && Object.keys(campaign.filters).length > 0 && (
        <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-4">
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
            Audience Filters
          </h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(campaign.filters).map(([k, v]) => (
              <span
                key={k}
                className="text-xs bg-slate-700 text-slate-300 px-2.5 py-1 rounded-full"
              >
                {k}: {String(v)}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Export section */}
      <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
          <FileDown size={15} />
          Export Audience
        </h2>

        {!canExport && (
          <p className="text-sm text-slate-500">Activate the campaign to enable exports.</p>
        )}

        {canExport && (
          <div className="flex items-center gap-3">
            <select
              value={selectedFormat}
              onChange={(e) => setSelectedFormat(e.target.value as ExportFormat)}
              className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              {(Object.keys(FORMAT_LABELS) as ExportFormat[]).map((f) => (
                <option key={f} value={f}>
                  {FORMAT_LABELS[f]}
                </option>
              ))}
            </select>
            <button
              onClick={() => exportMutation.mutate()}
              disabled={exportMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {exportMutation.isPending ? <RefreshCw size={14} className="animate-spin" /> : <Download size={14} />}
              Generate Export
            </button>
          </div>
        )}
      </div>

      {/* Export history */}
      {campaign.exports.length > 0 && (
        <div className="bg-slate-800/60 border border-slate-700/60 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-700">
            <h2 className="text-sm font-semibold text-slate-100">Export History</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-xs text-slate-500 uppercase tracking-wider">
                <th className="px-5 py-2.5 text-left font-medium">Format</th>
                <th className="px-5 py-2.5 text-left font-medium">Profiles</th>
                <th className="px-5 py-2.5 text-left font-medium">Status</th>
                <th className="px-5 py-2.5 text-left font-medium">Date</th>
                <th className="px-5 py-2.5 text-left font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {campaign.exports.map((ex) => (
                <tr key={ex.id} className="border-b border-slate-800 last:border-0">
                  <td className="px-5 py-3 text-slate-300">{FORMAT_LABELS[ex.format]}</td>
                  <td className="px-5 py-3 text-slate-400">
                    {ex.profile_count?.toLocaleString() ?? '—'}
                  </td>
                  <td className={cn('px-5 py-3 capitalize font-medium', STATUS_STYLE[ex.status])}>
                    {ex.status}
                    {ex.status === 'processing' && (
                      <RefreshCw size={12} className="inline ml-1.5 animate-spin" />
                    )}
                  </td>
                  <td className="px-5 py-3 text-slate-500">
                    {new Date(ex.created_at).toLocaleString()}
                  </td>
                  <td className="px-5 py-3">
                    {ex.status === 'ready' && (
                      <a
                        href={campaignsApi.downloadUrl(campaign.id, ex.id)}
                        download
                        className="flex items-center gap-1.5 text-brand-400 hover:text-brand-300 text-xs font-medium"
                      >
                        <Download size={13} />
                        Download
                      </a>
                    )}
                    {ex.status === 'failed' && ex.error_message && (
                      <span className="text-xs text-red-400" title={ex.error_message}>
                        Failed
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
