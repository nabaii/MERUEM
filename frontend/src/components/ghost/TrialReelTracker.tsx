import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, CheckCircle2, Clock, XCircle, TrendingUp } from 'lucide-react'
import toast from 'react-hot-toast'
import { ghostViralityApi, type TrialReel } from '../../api/ghostVirality'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card, CardHeader, CardTitle } from '../ui/Card'
import { timeAgo } from '../../lib/utils'

const STATUS_CONFIG: Record<string, { icon: typeof Clock; color: 'gray' | 'blue' | 'green' | 'red'; iconClass: string }> = {
  pending:  { icon: Clock, color: 'gray', iconClass: 'text-slate-400' },
  live:     { icon: TrendingUp, color: 'blue', iconClass: 'text-blue-400' },
  promoted: { icon: CheckCircle2, color: 'green', iconClass: 'text-emerald-400' },
  rejected: { icon: XCircle, color: 'red', iconClass: 'text-red-400' },
}

interface Props {
  ghostPostId?: string
  niche?: string
}

export function TrialReelTracker({ ghostPostId, niche }: Props) {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({
    variation_label: '',
    post_url: '',
    notes: '',
  })
  const [metricsForm, setMetricsForm] = useState({
    completion_rate: '',
    views_at_1k: '',
    likes: '',
    comments: '',
    shares: '',
  })

  const { data: trials = [], isLoading } = useQuery({
    queryKey: ['trial-reels', niche],
    queryFn: () => ghostViralityApi.listTrialReels(niche),
  })

  const createMut = useMutation({
    mutationFn: () =>
      ghostViralityApi.createTrialReel({
        ghost_post_id: ghostPostId,
        niche,
        variation_label: form.variation_label || undefined,
        post_url: form.post_url || undefined,
        notes: form.notes || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trial-reels'] })
      qc.invalidateQueries({ queryKey: ['ghost-stats'] })
      setShowForm(false)
      setForm({ variation_label: '', post_url: '', notes: '' })
      toast.success('Trial reel logged')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof ghostViralityApi.updateTrialReel>[1] }) =>
      ghostViralityApi.updateTrialReel(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trial-reels'] })
      qc.invalidateQueries({ queryKey: ['ghost-stats'] })
      setEditId(null)
      toast.success('Metrics updated')
    },
    onError: (e: Error) => toast.error(e.message),
  })

  function submitMetrics(trial: TrialReel) {
    const data: Parameters<typeof ghostViralityApi.updateTrialReel>[1] = {
      status: 'live',
    }
    if (metricsForm.completion_rate) data.completion_rate = parseFloat(metricsForm.completion_rate) / 100
    if (metricsForm.views_at_1k) data.views_at_1k = parseInt(metricsForm.views_at_1k)
    if (metricsForm.likes) data.likes = parseInt(metricsForm.likes)
    if (metricsForm.comments) data.comments = parseInt(metricsForm.comments)
    if (metricsForm.shares) data.shares = parseInt(metricsForm.shares)
    updateMut.mutate({ id: trial.id, data })
  }

  // Only show trials related to this ghost post if ghostPostId is provided
  const filtered = ghostPostId
    ? trials.filter(t => t.ghost_post_id === ghostPostId)
    : trials

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Trial Reels</CardTitle>
          <Button size="sm" onClick={() => setShowForm(v => !v)}>
            <Plus size={14} />
            Log Trial Reel
          </Button>
        </div>
      </CardHeader>

      {showForm && (
        <div className="mb-5 rounded-lg border border-slate-600 bg-slate-700/40 p-4 space-y-3">
          <p className="text-xs font-semibold text-slate-300 uppercase tracking-wide">New Trial Reel</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="text-xs text-slate-500 mb-1 block">Variation label</label>
              <input
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500"
                placeholder="e.g. Variation A"
                value={form.variation_label}
                onChange={e => setForm(f => ({ ...f, variation_label: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-xs text-slate-500 mb-1 block">Post URL</label>
              <input
                className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500"
                placeholder="https://instagram.com/reel/…"
                value={form.post_url}
                onChange={e => setForm(f => ({ ...f, post_url: e.target.value }))}
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-500 mb-1 block">Notes</label>
            <textarea
              rows={2}
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500 resize-none"
              placeholder="Optional notes…"
              value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            />
          </div>
          <div className="flex gap-2">
            <Button size="sm" loading={createMut.isPending} onClick={() => createMut.mutate()}>
              Save
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-slate-500 py-4">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-slate-500 py-4 text-center">
          No trial reels logged yet for this post.
        </p>
      ) : (
        <div className="space-y-3">
          {filtered.map(trial => {
            const cfg = STATUS_CONFIG[trial.status] ?? STATUS_CONFIG.pending
            const Icon = cfg.icon
            return (
              <div
                key={trial.id}
                className="rounded-lg border border-slate-700 bg-slate-700/30 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Icon size={15} className={cfg.iconClass} />
                    <span className="text-sm font-medium text-slate-200">
                      {trial.variation_label ?? 'Trial Reel'}
                    </span>
                    {trial.green_light && (
                      <Badge color="green">Green Light</Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge color={cfg.color}>{trial.status}</Badge>
                    {trial.status === 'pending' && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          setEditId(trial.id)
                          setMetricsForm({ completion_rate: '', views_at_1k: '', likes: '', comments: '', shares: '' })
                        }}
                      >
                        Enter metrics
                      </Button>
                    )}
                  </div>
                </div>

                {trial.post_url && (
                  <a
                    href={trial.post_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-brand-400 hover:underline mt-1 block truncate"
                  >
                    {trial.post_url}
                  </a>
                )}

                {/* Metrics grid */}
                {(trial.completion_rate != null || trial.views_at_1k != null) && (
                  <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
                    <Metric label="Completion" value={
                      trial.completion_rate != null
                        ? `${(trial.completion_rate * 100).toFixed(0)}%`
                        : null
                    } highlight={trial.completion_rate != null && trial.completion_rate >= 0.85} />
                    <Metric label="Views @1K" value={trial.views_at_1k?.toLocaleString() ?? null} />
                    <Metric label="Likes" value={trial.likes?.toLocaleString() ?? null} />
                    <Metric label="Comments" value={trial.comments?.toLocaleString() ?? null} />
                    <Metric label="Shares" value={trial.shares?.toLocaleString() ?? null} />
                  </div>
                )}

                {/* Inline metrics entry form */}
                {editId === trial.id && (
                  <div className="mt-3 rounded-lg border border-slate-600 bg-slate-800/60 p-3 space-y-2">
                    <p className="text-xs text-slate-400">Enter 24h performance metrics</p>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                      {(
                        [
                          { key: 'completion_rate', label: 'Completion %' },
                          { key: 'views_at_1k', label: 'Views @1K' },
                          { key: 'likes', label: 'Likes' },
                          { key: 'comments', label: 'Comments' },
                          { key: 'shares', label: 'Shares' },
                        ] as const
                      ).map(({ key, label }) => (
                        <div key={key}>
                          <label className="text-xs text-slate-500 mb-0.5 block">{label}</label>
                          <input
                            type="number"
                            className="w-full rounded border border-slate-600 bg-slate-900 px-2 py-1.5 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
                            value={metricsForm[key]}
                            onChange={e => setMetricsForm(f => ({ ...f, [key]: e.target.value }))}
                          />
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-2 pt-1">
                      <Button
                        size="sm"
                        loading={updateMut.isPending}
                        onClick={() => submitMetrics(trial)}
                      >
                        Save
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setEditId(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}

                <p className="text-xs text-slate-600 mt-2">{timeAgo(trial.created_at)}</p>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}

function Metric({ label, value, highlight }: { label: string; value: string | null; highlight?: boolean }) {
  if (!value) return null
  return (
    <div className="text-center">
      <p className={`text-base font-bold ${highlight ? 'text-emerald-400' : 'text-slate-200'}`}>{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  )
}
