import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { PageSpinner } from '../components/ui/Spinner'
import { Key, Copy, RefreshCw, Check } from 'lucide-react'
import toast from 'react-hot-toast'

export function SettingsPage() {
  const account = useAuthStore((s) => s.account)
  const [apiKey, setApiKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const { mutate: generateKey, isPending } = useMutation({
    mutationFn: authApi.generateApiKey,
    onSuccess: (data) => {
      setApiKey(data.api_key)
      toast.success('New API key generated')
    },
    onError: () => toast.error('Failed to generate API key'),
  })

  async function copyKey() {
    if (!apiKey) return
    await navigator.clipboard.writeText(apiKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!account) return <PageSpinner />

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
        <p className="text-sm text-slate-400 mt-1">Account and API access</p>
      </div>

      {/* Account info */}
      <Card>
        <CardHeader><CardTitle>Account</CardTitle></CardHeader>
        <dl className="space-y-3">
          <div className="flex justify-between text-sm">
            <dt className="text-slate-400">Email</dt>
            <dd className="text-slate-200">{account.email}</dd>
          </div>
          <div className="flex justify-between text-sm">
            <dt className="text-slate-400">Name</dt>
            <dd className="text-slate-200">{account.full_name ?? '—'}</dd>
          </div>
          <div className="flex justify-between text-sm items-center">
            <dt className="text-slate-400">Role</dt>
            <dd>
              <Badge color={account.role === 'admin' ? 'purple' : 'blue'} className="capitalize">
                {account.role}
              </Badge>
            </dd>
          </div>
        </dl>
      </Card>

      {/* API Key management */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key size={16} className="text-brand-400" /> API Key
          </CardTitle>
        </CardHeader>
        <p className="text-sm text-slate-400 mb-4">
          Use your API key as a Bearer token to authenticate programmatic requests.
          Regenerating will immediately invalidate the previous key.
        </p>

        {apiKey ? (
          <div className="bg-slate-900 border border-slate-700 rounded-lg px-4 py-3 flex items-center justify-between gap-3">
            <code className="text-sm text-brand-300 font-mono truncate">{apiKey}</code>
            <button
              onClick={copyKey}
              className="flex-shrink-0 text-slate-400 hover:text-slate-100 transition-colors"
            >
              {copied ? <Check size={16} className="text-emerald-400" /> : <Copy size={16} />}
            </button>
          </div>
        ) : (
          <p className="text-sm text-slate-500 mb-4">
            Your current API key is hidden. Generate a new one below.
          </p>
        )}

        <Button
          variant="secondary"
          loading={isPending}
          onClick={() => generateKey()}
          className="mt-4 flex items-center gap-2"
        >
          <RefreshCw size={15} /> {apiKey ? 'Rotate' : 'Generate'} API key
        </Button>
      </Card>

      {/* Placeholder billing */}
      <Card>
        <CardHeader><CardTitle>Usage & billing</CardTitle></CardHeader>
        <p className="text-sm text-slate-500">
          Billing and usage quotas will be available in a future release.
        </p>
      </Card>
    </div>
  )
}
