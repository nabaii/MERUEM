import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { profilesApi } from '../api/profiles'
import { InterestBars } from '../components/profiles/InterestBars'
import { SentimentBadge } from '../components/profiles/SentimentBadge'
import { ProfileCard } from '../components/profiles/ProfileCard'
import { Card, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { PageSpinner } from '../components/ui/Spinner'
import { formatNumber, timeAgo } from '../lib/utils'
import { Users, MapPin, ArrowLeft, Twitter, ExternalLink } from 'lucide-react'
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { TOPIC_COLORS } from '../lib/utils'

export function ProfileDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile', id],
    queryFn: () => profilesApi.get(id!),
    enabled: !!id,
  })

  if (isLoading) return <PageSpinner />
  if (!profile) return <p className="text-slate-400">Profile not found.</p>

  const radarData = profile.interests.slice(0, 8).map((i) => ({
    topic: i.topic,
    value: Math.round(i.confidence * 100),
  }))

  return (
    <div className="space-y-6 max-w-5xl">
      <Link to="/explorer" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200">
        <ArrowLeft size={15} /> Back to Explorer
      </Link>

      {/* Header card */}
      <Card>
        <div className="flex items-start gap-5">
          {profile.profile_image_url ? (
            <img
              src={profile.profile_image_url}
              alt={profile.display_name ?? ''}
              className="w-16 h-16 rounded-full object-cover flex-shrink-0"
            />
          ) : (
            <div className="w-16 h-16 rounded-full bg-slate-700 flex items-center justify-center">
              <Users size={24} className="text-slate-500" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-xl font-bold text-slate-100">
                {profile.display_name ?? profile.username ?? profile.platform_user_id}
              </h1>
              <Badge color="blue" className="capitalize">{profile.platform}</Badge>
              {profile.cluster_id != null && (
                <Link to={`/clusters/${profile.cluster_id}`}>
                  <Badge color="purple">Cluster {profile.cluster_id}</Badge>
                </Link>
              )}
            </div>
            {profile.username && (
              <p className="text-sm text-slate-500 mt-0.5">@{profile.username}</p>
            )}
            {profile.bio && (
              <p className="mt-2 text-sm text-slate-300 max-w-2xl">{profile.bio}</p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-slate-500">
              <span className="flex items-center gap-1">
                <Users size={13} /> {formatNumber(profile.follower_count)} followers
              </span>
              <span>{formatNumber(profile.following_count)} following</span>
              {profile.location_inferred && (
                <span className="flex items-center gap-1">
                  <MapPin size={13} /> {profile.location_inferred}
                </span>
              )}
              <span>Last collected {timeAgo(profile.last_collected)}</span>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Interests bar list */}
        <Card>
          <CardHeader><CardTitle>Interests</CardTitle></CardHeader>
          <InterestBars interests={profile.interests} />
        </Card>

        {/* Interest radar */}
        {radarData.length > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle>Interest radar</CardTitle></CardHeader>
            <ResponsiveContainer width="100%" height={250}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#334155" />
                <PolarAngleAxis dataKey="topic" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                />
                <Radar dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.25} />
              </RadarChart>
            </ResponsiveContainer>
          </Card>
        )}
      </div>

      {/* Recent posts */}
      {profile.recent_posts.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Recent posts</CardTitle></CardHeader>
          <ul className="divide-y divide-slate-700/50">
            {profile.recent_posts.map((post) => (
              <li key={post.id} className="py-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm text-slate-300 flex-1">{post.content}</p>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <SentimentBadge score={post.sentiment_score} />
                  </div>
                </div>
                <div className="mt-1.5 flex gap-3 text-xs text-slate-500">
                  {post.likes != null && <span>♥ {post.likes}</span>}
                  {post.reposts != null && <span>↺ {post.reposts}</span>}
                  <span>{timeAgo(post.posted_at)}</span>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Linked profiles */}
      {profile.linked_profiles.length > 0 && (
        <div>
          <h2 className="text-base font-semibold text-slate-100 mb-3">Linked profiles</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {profile.linked_profiles.map((p) => (
              <ProfileCard key={p.id} profile={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
