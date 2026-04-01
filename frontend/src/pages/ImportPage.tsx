import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Upload,
  Link,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Plus,
  Server,
  Shield,
  Trash2,
  RotateCcw,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import {
  uploadCsv,
  enrichSingleUrl,
  enrichBulkUrls,
  listImportJobs,
  getProxyStats,
  getSessionStats,
  addProxy,
  removeProxy,
  resetProxy,
  addSession,
  invalidateSession,
  type ImportJob,
} from '../api/imports'

// ── Helpers ───────────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: ImportJob['status'] }) {
  const map = {
    pending: { icon: Clock, color: 'text-yellow-400 bg-yellow-400/10', label: 'Pending' },
    running: { icon: Loader2, color: 'text-blue-400 bg-blue-400/10', label: 'Running' },
    completed: { icon: CheckCircle2, color: 'text-emerald-400 bg-emerald-400/10', label: 'Done' },
    failed: { icon: XCircle, color: 'text-red-400 bg-red-400/10', label: 'Failed' },
  } as const
  const { icon: Icon, color, label } = map[status] ?? map.pending
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${color}`}>
      <Icon size={12} className={status === 'running' ? 'animate-spin' : ''} />
      {label}
    </span>
  )
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-NG', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

// ── Section: CSV Upload ───────────────────────────────────────────────────────

function CsvUploadSection({ onJobCreated }: { onJobCreated: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [defaultPlatform, setDefaultPlatform] = useState('unknown')
  const [enrichViaBot, setEnrichViaBot] = useState(false)
  const [dragging, setDragging] = useState(false)

  const mutation = useMutation({
    mutationFn: () => uploadCsv(file!, defaultPlatform, enrichViaBot),
    onSuccess: () => {
      toast.success('CSV import job queued')
      setFile(null)
      onJobCreated()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }

  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <Upload size={18} className="text-brand-400" />
        <h2 className="text-sm font-semibold text-slate-200">CSV / Excel Upload</h2>
      </div>
      <p className="text-xs text-slate-500">
        Upload a spreadsheet with columns like <code className="text-slate-400">username</code>,{' '}
        <code className="text-slate-400">platform</code>, <code className="text-slate-400">follower_count</code>,{' '}
        <code className="text-slate-400">profile_url</code>, etc.
      </p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
        className={`
          border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
          ${dragging ? 'border-brand-500 bg-brand-500/5' : 'border-slate-700 hover:border-slate-500'}
        `}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <p className="text-sm text-slate-200 font-medium">{file.name}</p>
        ) : (
          <>
            <Upload size={28} className="mx-auto mb-2 text-slate-600" />
            <p className="text-sm text-slate-400">Drop a CSV or Excel file here, or click to browse</p>
            <p className="text-xs text-slate-600 mt-1">.csv · .xlsx · .xls · max 20 MB</p>
          </>
        )}
      </div>

      {/* Options */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1.5">Default platform</label>
          <select
            value={defaultPlatform}
            onChange={(e) => setDefaultPlatform(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            {['unknown', 'twitter', 'instagram', 'facebook', 'tiktok', 'linkedin', 'whatsapp'].map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={enrichViaBot}
              onChange={(e) => setEnrichViaBot(e.target.checked)}
              className="w-4 h-4 rounded border-slate-600 bg-slate-800 accent-brand-500"
            />
            <span className="text-sm text-slate-300">Enrich via bot</span>
          </label>
        </div>
      </div>

      <Button
        onClick={() => mutation.mutate()}
        disabled={!file || mutation.isPending}
        className="w-full"
      >
        {mutation.isPending ? (
          <><Loader2 size={15} className="animate-spin" /> Uploading…</>
        ) : (
          <><Upload size={15} /> Import File</>
        )}
      </Button>
    </Card>
  )
}

// ── Section: URL Enrichment ───────────────────────────────────────────────────

function UrlEnrichSection({ onJobCreated }: { onJobCreated: () => void }) {
  const [urlInput, setUrlInput] = useState('')
  const [bulkUrls, setBulkUrls] = useState('')
  const [tab, setTab] = useState<'single' | 'bulk'>('single')

  const singleMutation = useMutation({
    mutationFn: () => enrichSingleUrl(urlInput.trim()),
    onSuccess: () => {
      toast.success('Enrichment job queued')
      setUrlInput('')
      onJobCreated()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const bulkMutation = useMutation({
    mutationFn: () => {
      const urls = bulkUrls.split('\n').map((u) => u.trim()).filter(Boolean)
      return enrichBulkUrls(urls)
    },
    onSuccess: () => {
      toast.success('Bulk enrichment job queued')
      setBulkUrls('')
      onJobCreated()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <Link size={18} className="text-brand-400" />
        <h2 className="text-sm font-semibold text-slate-200">URL Enrichment</h2>
      </div>
      <p className="text-xs text-slate-500">
        Paste a TikTok, LinkedIn, Instagram, Twitter, or Facebook profile URL.
        The bot visits and scrapes profile data automatically.
      </p>

      {/* Tab switcher */}
      <div className="flex gap-1 bg-slate-800/50 p-1 rounded-lg w-fit">
        {(['single', 'bulk'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize ${
              tab === t
                ? 'bg-slate-700 text-slate-100'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            {t === 'single' ? 'Single URL' : 'Bulk (one per line)'}
          </button>
        ))}
      </div>

      {tab === 'single' ? (
        <div className="space-y-3">
          <Input
            placeholder="https://www.tiktok.com/@username"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
          />
          <Button
            onClick={() => singleMutation.mutate()}
            disabled={!urlInput.trim() || singleMutation.isPending}
            className="w-full"
          >
            {singleMutation.isPending ? (
              <><Loader2 size={15} className="animate-spin" /> Enriching…</>
            ) : (
              <><RefreshCw size={15} /> Enrich Profile</>
            )}
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <textarea
            rows={6}
            placeholder={"https://www.tiktok.com/@brand1\nhttps://linkedin.com/in/ceo-name\nhttps://www.instagram.com/handle"}
            value={bulkUrls}
            onChange={(e) => setBulkUrls(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500 resize-none font-mono"
          />
          <p className="text-xs text-slate-600">
            {bulkUrls.split('\n').filter((l) => l.trim()).length} URLs · max 200
          </p>
          <Button
            onClick={() => bulkMutation.mutate()}
            disabled={!bulkUrls.trim() || bulkMutation.isPending}
            className="w-full"
          >
            {bulkMutation.isPending ? (
              <><Loader2 size={15} className="animate-spin" /> Queuing…</>
            ) : (
              <><RefreshCw size={15} /> Enrich All URLs</>
            )}
          </Button>
        </div>
      )}
    </Card>
  )
}

// ── Section: Recent Jobs ──────────────────────────────────────────────────────

function RecentJobsSection({ refetchKey }: { refetchKey: number }) {
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['importJobs', refetchKey],
    queryFn: () => listImportJobs(15),
    refetchInterval: 8000,
  })

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 size={16} className="animate-spin" /> Loading jobs…
        </div>
      </Card>
    )
  }

  return (
    <Card className="p-6">
      <h2 className="text-sm font-semibold text-slate-200 mb-4">Recent Import Jobs</h2>
      {jobs.length === 0 ? (
        <p className="text-sm text-slate-600">No import jobs yet.</p>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-slate-800/40 border border-slate-700/50"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <StatusBadge status={job.status} />
                  <span className="text-xs text-slate-400 capitalize">{job.platform}</span>
                </div>
                <p className="text-xs text-slate-600 truncate">
                  {formatDate(job.created_at)}
                  {job.error_message && (
                    <span className="text-red-400 ml-2">{job.error_message.slice(0, 60)}</span>
                  )}
                </p>
              </div>
              <div className="text-right shrink-0 ml-4">
                <p className="text-sm font-semibold text-slate-200">{job.profiles_collected}</p>
                <p className="text-xs text-slate-600">profiles</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

// ── Section: Proxy Pool ───────────────────────────────────────────────────────

function ProxyPoolSection() {
  const qc = useQueryClient()
  const { data: stats } = useQuery({
    queryKey: ['proxyStats'],
    queryFn: getProxyStats,
    refetchInterval: 30_000,
  })

  const [proxyUrl, setProxyUrl] = useState('')
  const [carrier, setCarrier] = useState('mtn')
  const [proxyType, setProxyType] = useState('mobile')

  const addMut = useMutation({
    mutationFn: () => addProxy({ url: proxyUrl.trim(), carrier, proxy_type: proxyType }),
    onSuccess: () => {
      toast.success('Proxy added')
      setProxyUrl('')
      qc.invalidateQueries({ queryKey: ['proxyStats'] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Server size={18} className="text-brand-400" />
        <h2 className="text-sm font-semibold text-slate-200">Proxy Pool</h2>
        {stats && (
          <span className="ml-auto text-xs text-slate-500">
            {stats.active}/{stats.total} active
          </span>
        )}
      </div>

      {stats && Object.keys(stats.by_carrier).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(stats.by_carrier).map(([carrier, count]) => (
            <span key={carrier} className="px-2 py-0.5 rounded bg-slate-800 text-xs text-slate-400">
              {carrier}: {count}
            </span>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <Input
          placeholder="socks5://user:pass@host:port"
          value={proxyUrl}
          onChange={(e) => setProxyUrl(e.target.value)}
          className="font-mono text-xs"
        />
        <div className="grid grid-cols-2 gap-2">
          <select
            value={carrier}
            onChange={(e) => setCarrier(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            {['mtn', 'airtel', 'glo', '9mobile', 'residential', 'datacenter', 'other'].map((c) => (
              <option key={c} value={c}>{c.toUpperCase()}</option>
            ))}
          </select>
          <select
            value={proxyType}
            onChange={(e) => setProxyType(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="mobile">Mobile</option>
            <option value="residential">Residential</option>
            <option value="datacenter">Datacenter</option>
          </select>
        </div>
        <Button
          onClick={() => addMut.mutate()}
          disabled={!proxyUrl.trim() || addMut.isPending}
          className="w-full"
          variant="secondary"
        >
          <Plus size={14} /> Add Proxy
        </Button>
      </div>
    </Card>
  )
}

// ── Section: Session Pool ─────────────────────────────────────────────────────

function SessionPoolSection() {
  const qc = useQueryClient()
  const { data: stats } = useQuery({
    queryKey: ['sessionStats'],
    queryFn: getSessionStats,
    refetchInterval: 30_000,
  })

  const [platform, setPlatform] = useState('tiktok')
  const [cookiesJson, setCookiesJson] = useState('')
  const [userAgent, setUserAgent] = useState('')

  const addMut = useMutation({
    mutationFn: () => {
      const cookies = JSON.parse(cookiesJson)
      return addSession({ platform, cookies, user_agent: userAgent })
    },
    onSuccess: () => {
      toast.success('Session registered')
      setCookiesJson('')
      setUserAgent('')
      qc.invalidateQueries({ queryKey: ['sessionStats'] })
    },
    onError: (e: Error) => toast.error(`Session add failed: ${e.message}`),
  })

  return (
    <Card className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Shield size={18} className="text-brand-400" />
        <h2 className="text-sm font-semibold text-slate-200">Session Pool</h2>
        {stats && (
          <span className="ml-auto text-xs text-slate-500">
            {stats.active}/{stats.total} active
          </span>
        )}
      </div>

      {stats && Object.keys(stats.by_platform).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(stats.by_platform).map(([plat, count]) => (
            <span key={plat} className="px-2 py-0.5 rounded bg-slate-800 text-xs text-slate-400">
              {plat}: {count}
            </span>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-600">
        Paste cookies from a Playwright <code>context.cookies()</code> call after manual login.
      </p>

      <div className="space-y-2">
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          {['tiktok', 'linkedin', 'instagram', 'twitter', 'facebook'].map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <textarea
          rows={4}
          placeholder='[{"name":"sessionid","value":"...","domain":".tiktok.com",...}]'
          value={cookiesJson}
          onChange={(e) => setCookiesJson(e.target.value)}
          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-brand-500 resize-none font-mono"
        />
        <Input
          placeholder="Mozilla/5.0 (Linux; Android 13; ...) Chrome/121..."
          value={userAgent}
          onChange={(e) => setUserAgent(e.target.value)}
          className="text-xs font-mono"
        />
        <Button
          onClick={() => addMut.mutate()}
          disabled={!cookiesJson.trim() || !userAgent.trim() || addMut.isPending}
          className="w-full"
          variant="secondary"
        >
          <Plus size={14} /> Register Session
        </Button>
      </div>
    </Card>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function ImportPage() {
  const [refetchKey, setRefetchKey] = useState(0)
  const triggerRefetch = () => setRefetchKey((k) => k + 1)

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-100">Data Import</h1>
        <p className="text-sm text-slate-500 mt-1">
          Ingest profiles via CSV upload, URL enrichment, or trigger bot collection jobs.
        </p>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CsvUploadSection onJobCreated={triggerRefetch} />
        <UrlEnrichSection onJobCreated={triggerRefetch} />
      </div>

      {/* Jobs table */}
      <RecentJobsSection refetchKey={refetchKey} />

      {/* Infrastructure */}
      <div>
        <h2 className="text-base font-semibold text-slate-200 mb-4">Bot Infrastructure</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ProxyPoolSection />
          <SessionPoolSection />
        </div>
      </div>
    </div>
  )
}
