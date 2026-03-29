import { api } from './client'
import type { Profile } from './profiles'

export interface Cluster {
  id: number
  label: string | null
  description: string | null
  member_count: number
  top_interests: Record<string, number> | null
  last_updated: string
}

export interface ClusterListResponse {
  total: number
  items: Cluster[]
}

export interface ClusterProfilesResponse {
  cluster_id: number
  total: number
  limit: number
  offset: number
  items: Profile[]
}

export interface LookalikeRequest {
  seed_profile_ids?: string[]
  seed_cluster_id?: number
  limit?: number
  platform?: string
  min_followers?: number
  max_followers?: number
  location?: string
}

export interface LookalikeCandidate {
  profile_id: string
  username: string | null
  display_name: string | null
  platform: string
  follower_count: number | null
  location_inferred: string | null
  similarity_score: number
}

export interface LookalikeResponse {
  seed_profile_count: number
  seed_cluster_id: number | null
  results: LookalikeCandidate[]
}

export const clustersApi = {
  list: () => api.get<ClusterListResponse>('/clusters'),
  get: (id: number) => api.get<Cluster>(`/clusters/${id}`),
  profiles: (id: number, limit = 50, offset = 0) =>
    api.get<ClusterProfilesResponse>(`/clusters/${id}/profiles?limit=${limit}&offset=${offset}`),
  lookalike: (body: LookalikeRequest) => api.post<LookalikeResponse>('/lookalike', body),
}
