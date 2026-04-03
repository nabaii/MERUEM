import { api } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GhostScoutJob {
  id: string
  niche: string
  competitor_accounts: string[] | null
  status: 'pending' | 'running' | 'completed' | 'failed'
  celery_task_id: string | null
  reels_scraped: number
  ghost_viral_found: number
  error_message: string | null
  created_by: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface PatternCard {
  id: string
  ghost_post_id: string
  hook_duration_seconds: number | null
  hook_clip_path: string | null
  scene_cut_count: number | null
  transcript_snippet: string | null
  transcript_language: string | null
  transcript_confidence: number | null
  visual_text: string | null
  audio_type: 'trending' | 'original' | 'unknown' | null
  audio_id: string | null
  audio_name: string | null
  hook_archetype: string | null
  raw_card: Record<string, unknown> | null
  created_at: string
}

export interface GhostViralPost {
  id: string
  reel_id: string
  account_username: string
  niche: string | null
  view_count: number | null
  like_count: number | null
  comment_count: number | null
  follower_count: number | null
  outlier_reach_ratio: number | null
  ghost_virality_delta: number | null
  like_percentile: number | null
  view_velocity: number | null
  like_velocity: number | null
  strategy_label: 'high_dm_share' | 'watch_time_arbitrage' | 'audio_driven' | 'polarizing' | 'utility' | 'unknown' | null
  comment_sentiment: string | null
  permalink: string | null
  thumbnail_url: string | null
  posted_at: string | null
  pattern_card_ready: boolean
  detected_at: string
  pattern_card: PatternCard | null
}

export interface NicheOverview {
  niche: string
  sample_size: number
  p10: number | null
  p30: number | null
  p50: number | null
  p70: number | null
  p90: number | null
  outlier_reach_threshold: number
  ghost_viral_count: number | null
  updated_at: string
}

export interface TrialReel {
  id: string
  ghost_post_id: string | null
  niche: string | null
  variation_label: string | null
  post_url: string | null
  views_at_1k: number | null
  completion_rate: number | null
  likes: number | null
  comments: number | null
  shares: number | null
  status: 'pending' | 'live' | 'promoted' | 'rejected'
  green_light: boolean
  notes: string | null
  posted_at: string | null
  measured_at: string | null
  created_by: string | null
  created_at: string
}

export interface GhostViralityStats {
  total_ghost_posts: number
  new_last_7_days: number
  pattern_cards_ready: number
  active_scout_jobs: number
  trial_reels_total: number
  trial_reels_green_lit: number
  top_niches: { niche: string; count: number }[]
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const ghostViralityApi = {
  // Stats
  getStats: () => api.get<GhostViralityStats>('/ghost-virality/stats'),

  // Scout jobs
  createScoutJob: (niche: string, competitorAccounts: string[]) =>
    api.post<GhostScoutJob>('/ghost-virality/scout-jobs', {
      niche,
      competitor_accounts: competitorAccounts,
    }),
  listScoutJobs: (limit = 20) =>
    api.get<GhostScoutJob[]>(`/ghost-virality/scout-jobs?limit=${limit}`),
  getScoutJob: (id: string) =>
    api.get<GhostScoutJob>(`/ghost-virality/scout-jobs/${id}`),

  // Ghost Feed
  listGhosts: (params: {
    niche?: string
    strategy?: string
    days?: number
    limit?: number
    offset?: number
  } = {}) => {
    const q = new URLSearchParams()
    if (params.niche) q.set('niche', params.niche)
    if (params.strategy) q.set('strategy', params.strategy)
    if (params.days != null) q.set('days', String(params.days))
    if (params.limit != null) q.set('limit', String(params.limit))
    if (params.offset != null) q.set('offset', String(params.offset))
    return api.get<GhostViralPost[]>(`/ghost-virality/ghosts?${q}`)
  },
  getGhost: (id: string) => api.get<GhostViralPost>(`/ghost-virality/ghosts/${id}`),
  getPatternCard: (postId: string) =>
    api.get<PatternCard>(`/ghost-virality/ghosts/${postId}/pattern-card`),
  retryPatternRecognition: (postId: string) =>
    api.post<{ status: string; post_id: string }>(
      `/ghost-virality/ghosts/${postId}/pattern-card/retry`,
    ),

  // Niches
  listNiches: () => api.get<NicheOverview[]>('/ghost-virality/niches'),

  // Trial Reels
  createTrialReel: (data: {
    ghost_post_id?: string
    niche?: string
    variation_label?: string
    post_url?: string
    notes?: string
  }) => api.post<TrialReel>('/ghost-virality/trial-reels', data),
  listTrialReels: (niche?: string, limit = 50) => {
    const q = new URLSearchParams({ limit: String(limit) })
    if (niche) q.set('niche', niche)
    return api.get<TrialReel[]>(`/ghost-virality/trial-reels?${q}`)
  },
  getTrialReel: (id: string) => api.get<TrialReel>(`/ghost-virality/trial-reels/${id}`),
  updateTrialReel: (
    id: string,
    data: Partial<{
      post_url: string
      views_at_1k: number
      completion_rate: number
      likes: number
      comments: number
      shares: number
      status: string
      green_light: boolean
      notes: string
      posted_at: string
      measured_at: string
    }>,
  ) => api.patch<TrialReel>(`/ghost-virality/trial-reels/${id}`, data),
}
