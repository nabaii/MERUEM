import { api } from './client'

export interface Profile {
  id: string
  platform: string
  platform_user_id: string
  username: string | null
  display_name: string | null
  bio: string | null
  profile_image_url: string | null
  location_inferred: string | null
  follower_count: number | null
  following_count: number | null
  tweet_count: number | null
  cluster_id: number | null
  affinity_score: number | null
  last_collected: string | null
  created_at: string
}

export interface Interest {
  topic: string
  confidence: number
}

export interface PostSummary {
  id: string
  content: string | null
  post_type: string | null
  likes: number | null
  reposts: number | null
  sentiment_score: number | null
  posted_at: string | null
}

export interface ProfileDetail extends Profile {
  interests: Interest[]
  recent_posts: PostSummary[]
  linked_profiles: Profile[]
}

export interface ProfileListResponse {
  total: number
  limit: number
  offset: number
  items: Profile[]
}

export interface ProfileFilters {
  q?: string
  platform?: string
  cluster_id?: number
  interest?: string
  location?: string
  min_followers?: number
  max_followers?: number
  limit?: number
  offset?: number
}

function buildQuery(filters: ProfileFilters): string {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  })
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export const profilesApi = {
  list: (filters: ProfileFilters = {}) =>
    api.get<ProfileListResponse>(`/profiles${buildQuery(filters)}`),

  get: (id: string) => api.get<ProfileDetail>(`/profiles/${id}`),
}
