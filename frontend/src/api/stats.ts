import { api } from './client'

export interface PlatformCount {
  platform: string
  count: number
}

export interface RecentJob {
  id: string
  platform: string
  status: string
  profiles_collected: number
  created_at: string
}

export interface Stats {
  total_profiles: number
  total_posts: number
  total_clusters: number
  active_jobs: number
  profiles_by_platform: PlatformCount[]
  top_clusters: { id: number; label: string | null; member_count: number }[]
  recent_jobs: RecentJob[]
}

export const statsApi = {
  get: () => api.get<Stats>('/stats'),
}
