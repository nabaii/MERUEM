import { api } from './client'

export interface ImportJob {
  id: string
  platform: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  params: Record<string, unknown> | null
  celery_task_id: string | null
  profiles_collected: number
  error_message: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface ProxyStats {
  total: number
  active: number
  failed: number
  by_carrier: Record<string, number>
}

export interface SessionStats {
  total: number
  active: number
  by_platform: Record<string, number>
}

export interface AddProxyPayload {
  url: string
  carrier: string
  proxy_type: string
}

export interface AddSessionPayload {
  platform: string
  cookies: Record<string, unknown>[]
  user_agent: string
  proxy_id?: string
  account_age_days?: number
}

// ── CSV upload ────────────────────────────────────────────────────────────────

export async function uploadCsv(
  file: File,
  defaultPlatform = 'unknown',
  enrichViaBot = false,
): Promise<ImportJob> {
  const form = new FormData()
  form.append('file', file)
  form.append('default_platform', defaultPlatform)
  form.append('enrich_via_bot', String(enrichViaBot))

  const token = localStorage.getItem('meruem_token')
  const res = await fetch('/api/v1/import/csv', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'CSV upload failed')
  }
  return res.json()
}

// ── URL enrichment ────────────────────────────────────────────────────────────

export function enrichSingleUrl(url: string): Promise<ImportJob> {
  return api.post<ImportJob>('/import/enrich-url', { url })
}

export function enrichBulkUrls(urls: string[], useProxy = true): Promise<ImportJob> {
  return api.post<ImportJob>('/import/enrich-urls', { urls, use_proxy: useProxy })
}

// ── Job status ────────────────────────────────────────────────────────────────

export function listImportJobs(limit = 20): Promise<ImportJob[]> {
  return api.get<ImportJob[]>(`/import/jobs?limit=${limit}`)
}

export function getImportJob(id: string): Promise<ImportJob> {
  return api.get<ImportJob>(`/import/jobs/${id}`)
}

// ── Proxy pool ────────────────────────────────────────────────────────────────

export function getProxyStats(): Promise<ProxyStats> {
  return api.get<ProxyStats>('/import/proxies/stats')
}

export function addProxy(payload: AddProxyPayload): Promise<{ id: string; carrier: string; type: string }> {
  return api.post('/import/proxies', payload)
}

export function removeProxy(id: string): Promise<void> {
  return api.delete(`/import/proxies/${id}`)
}

export function resetProxy(id: string): Promise<{ status: string }> {
  return api.post(`/import/proxies/${id}/reset`)
}

// ── Session pool ──────────────────────────────────────────────────────────────

export function getSessionStats(): Promise<SessionStats> {
  return api.get<SessionStats>('/import/sessions/stats')
}

export function addSession(payload: AddSessionPayload): Promise<{ id: string; platform: string }> {
  return api.post('/import/sessions', payload)
}

export function invalidateSession(id: string): Promise<void> {
  return api.delete(`/import/sessions/${id}`)
}
