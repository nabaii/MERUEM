import { api } from './client'

export type CampaignStatus = 'draft' | 'active' | 'exported' | 'completed'
export type ExportFormat = 'meta' | 'twitter' | 'csv'
export type ExportStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface Campaign {
  id: string
  name: string
  owner_id: string | null
  status: CampaignStatus
  filters: Record<string, unknown> | null
  created_at: string
  updated_at: string
  audience_count: number
}

export interface CampaignDetail extends Campaign {
  exports: CampaignExport[]
}

export interface CampaignExport {
  id: string
  campaign_id: string
  format: ExportFormat
  profile_count: number | null
  status: ExportStatus
  file_key: string | null
  error_message: string | null
  created_at: string
}

export interface ReachEstimate {
  estimated_profiles: number
  filters_applied: Record<string, unknown>
}

export interface ReachFilters {
  platform?: string
  cluster_id?: number
  location?: string
  min_followers?: number
  max_followers?: number
}

function buildQuery(obj: Record<string, unknown>): string {
  const params = new URLSearchParams()
  Object.entries(obj).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  })
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export const campaignsApi = {
  list: (status?: CampaignStatus) =>
    api.get<Campaign[]>(`/campaigns${status ? `?status=${status}` : ''}`),

  get: (id: string) => api.get<CampaignDetail>(`/campaigns/${id}`),

  create: (body: { name: string; filters?: Record<string, unknown> }) =>
    api.post<Campaign>('/campaigns', body),

  update: (id: string, body: { name?: string; filters?: Record<string, unknown> }) =>
    api.patch<Campaign>(`/campaigns/${id}`, body),

  delete: (id: string) => api.delete<void>(`/campaigns/${id}`),

  activate: (id: string) => api.post<Campaign>(`/campaigns/${id}/activate`, {}),

  addProfiles: (id: string, profileIds: string[]) =>
    api.post<void>(`/campaigns/${id}/audiences`, profileIds),

  removeProfiles: (id: string, profileIds: string[]) =>
    api.delete<void>(`/campaigns/${id}/audiences`, profileIds),

  reachEstimate: (filters: ReachFilters) =>
    api.get<ReachEstimate>(`/campaigns/reach-estimate${buildQuery(filters as Record<string, unknown>)}`),

  createExport: (id: string, format: ExportFormat) =>
    api.post<CampaignExport>(`/campaigns/${id}/exports`, { format }),

  listExports: (id: string) => api.get<CampaignExport[]>(`/campaigns/${id}/exports`),

  downloadUrl: (campaignId: string, exportId: string) =>
    `/api/v1/campaigns/${campaignId}/exports/${exportId}/download`,
}
