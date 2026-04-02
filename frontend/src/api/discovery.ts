import { api } from './client'

// ── Types ──────────────────────────────────────────────────────────────────

export interface KeywordExpansionResponse {
  original: string[]
  expanded: string[]
}

export interface DiscoveredTweet {
  tweet_id: string
  content: string
  created_at: string | null
  likes: number
  retweets: number
  replies: number
  post_type: string | null
}

export interface PublicContactInfo {
  emails: string[]
  phone_numbers: string[]
  social_handles: string[]
  urls: string[]
}

export interface DiscoveredUser {
  platform_user_id: string
  user_id: string | null
  username: string
  display_name: string | null
  bio: string | null
  location_raw: string | null
  profile_image_url: string | null
  follower_count: number
  following_count: number
  tweet_count: number
  location_match: boolean
  relevance_score: number
  matching_tweets: DiscoveredTweet[]
  date_joined_twitter: string | null
  last_10_tweets: DiscoveredTweet[]
  user_type: string | null
  public_contact_info: PublicContactInfo
  engagement_frequency_score: number
  topic_relevance_score: number
  conversation_influence_score: number
  conversion_likelihood_score: number
  high_value_score: number
  high_value_band: string
  hybrid_signals: string[]
  actionable_insights: string[]
  recommended_angle: string | null
  manual_followers_note: string | null
  manual_followers_list: string[]
  manual_following_list: string[]
  manual_notes: string | null
}

export interface DiscoveryResponse {
  job_id: string
  status: string
  dummy_mode: boolean
  seed_keywords: string[]
  expanded_keywords: string[]
  location: string
  users: DiscoveredUser[]
  total_tweets_scanned: number
  total_users_found: number
  location_matched_count: number
  profiled_users_count: number
  high_value_users_found: number
  selected_micro_influencers: string[]
}

export interface DiscoveryJobSummary {
  id: string
  platform: string
  dummy_mode: boolean
  seed_keywords: string[]
  location: string
  status: string
  results_count: number
  tweets_scanned: number
  location_matched: number
  created_at: string
}

export interface DiscoveryHistoryResponse {
  jobs: DiscoveryJobSummary[]
}

export interface SaveUsersResponse {
  saved_count: number
  profile_ids: string[]
}

export interface DiscoveryUserManualEnrichmentPayload {
  followers_list: string[]
  following_list: string[]
  notes?: string | null
}

export interface SharedFollowingCandidate {
  username: string
  display_name: string | null
  overlap_count: number
  followed_by_users: string[]
  discovered_user_index: number | null
  follower_count: number | null
  high_value_score: number | null
  high_value_band: string | null
  user_type: string | null
  micro_influencer_fit_score: number
  reasons: string[]
  selected: boolean
}

export interface SharedFollowingsResponse {
  discovery_job_id: string
  analyzed_user_handles: string[]
  min_overlap: number
  total_candidates: number
  candidates: SharedFollowingCandidate[]
}

// ── API calls ──────────────────────────────────────────────────────────────

export const discoveryApi = {
  expandKeywords: (seeds: string[]) =>
    api.post<KeywordExpansionResponse>('/discovery/expand-keywords', {
      seed_keywords: seeds,
    }),

  search: (params: {
    seed_keywords: string[]
    expanded_keywords: string[]
    location: string
    date_from: string
    date_to: string
    max_results?: number
    dummy_mode?: boolean
  }) => api.post<DiscoveryResponse>('/discovery/search', params),

  saveUsers: (jobId: string, userIndices: number[]) =>
    api.post<SaveUsersResponse>('/discovery/save-users', {
      discovery_job_id: jobId,
      user_indices: userIndices,
    }),

  updateManualEnrichment: (
    jobId: string,
    userIndex: number,
    payload: DiscoveryUserManualEnrichmentPayload,
  ) => api.patch<DiscoveredUser>(`/discovery/${jobId}/users/${userIndex}/manual-enrichment`, payload),

  analyzeSharedFollowings: (
    jobId: string,
    payload: { user_indices: number[]; min_overlap?: number; max_candidates?: number },
  ) => api.post<SharedFollowingsResponse>(`/discovery/${jobId}/shared-followings/analyze`, payload),

  saveSharedFollowingSelection: (jobId: string, usernames: string[]) =>
    api.patch<SharedFollowingsResponse>(`/discovery/${jobId}/shared-followings/selection`, {
      usernames,
    }),

  getHistory: () =>
    api.get<DiscoveryHistoryResponse>('/discovery/history'),

  getJob: (jobId: string) =>
    api.get<DiscoveryResponse>(`/discovery/${jobId}`),

  downloadCsv: async (jobId: string) => {
    const token = localStorage.getItem('meruem_token')
    const response = await fetch(`/api/v1/discovery/${jobId}/export/csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!response.ok) {
      const body = await response.text().catch(() => '')
      throw new Error(body || 'Failed to export discovery CSV')
    }
    return response.blob()
  },
}
