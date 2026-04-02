import type { ReactNode } from 'react'
import {
  AtSign,
  Calendar,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Link2,
  Mail,
  MapPin,
  MessageSquare,
  Phone,
  Save,
  Star,
  Target,
  TrendingUp,
} from 'lucide-react'

import type { DiscoveredTweet, DiscoveredUser, SharedFollowingCandidate } from '../../api/discovery'
import { formatNumber } from '../../lib/utils'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { HIGH_VALUE_COLORS, formatDate, truncate } from './twitterDiscoveryUtils'

export function StatTile({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: string
}) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{formatNumber(value)}</p>
      <p className="text-xs text-slate-400 mt-1">{label}</p>
    </div>
  )
}

export function UserRow({
  user,
  selected,
  expanded,
  selectedAsMicroInfluencer,
  manualDraft,
  manualSaving,
  onToggleSelect,
  onToggleExpand,
  onManualDraftChange,
  onSaveManual,
}: {
  user: DiscoveredUser
  selected: boolean
  expanded: boolean
  selectedAsMicroInfluencer: boolean
  manualDraft: { followersText: string; followingText: string; notes: string }
  manualSaving: boolean
  onToggleSelect: () => void
  onToggleExpand: () => void
  onManualDraftChange: (patch: Partial<{ followersText: string; followingText: string; notes: string }>) => void
  onSaveManual: () => void
}) {
  const displayTweets = getDisplayTweets(user)

  return (
    <>
      <tr className="hover:bg-slate-700/30 transition-colors cursor-pointer" onClick={onToggleExpand}>
        <td className="py-3 pr-2 print:hidden" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="rounded border-slate-600 bg-slate-700 text-brand-600 focus:ring-brand-500"
          />
        </td>
        <td className="py-3">
          <div className="flex items-center gap-3">
            {user.profile_image_url ? (
              <img src={user.profile_image_url} alt="" className="w-9 h-9 rounded-full border border-slate-600" />
            ) : (
              <div className="w-9 h-9 rounded-full bg-slate-600 flex items-center justify-center text-xs font-bold text-slate-300">
                {user.username?.[0]?.toUpperCase() ?? '?'}
              </div>
            )}
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium text-slate-200">{user.display_name || user.username}</span>
                <Badge color={HIGH_VALUE_COLORS[user.high_value_band] ?? 'gray'}>{user.high_value_band}</Badge>
                {selectedAsMicroInfluencer && <Badge color="green">Micro-Influencer Pick</Badge>}
                <a
                  href={`https://x.com/${user.username}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-slate-500 hover:text-sky-400 transition-colors print:hidden"
                >
                  <ExternalLink size={12} />
                </a>
              </div>
              <p className="text-xs text-slate-500">@{user.username}</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Topic {Math.round(user.topic_relevance_score)} | Conversion {Math.round(user.conversion_likelihood_score)} | {displayTweets.length} tweets reviewed
              </p>
            </div>
          </div>
        </td>
        <td className="py-3">
          <span className="text-xs text-slate-300">{user.user_type || 'Unclassified'}</span>
        </td>
        <td className="py-3">
          {user.location_raw ? (
            <div className="flex items-center gap-1.5">
              <MapPin size={12} className={user.location_match ? 'text-emerald-400' : 'text-slate-500'} />
              <span className={user.location_match ? 'text-emerald-300 text-xs font-medium' : 'text-slate-400 text-xs'}>
                {user.location_raw}
              </span>
            </div>
          ) : (
            <span className="text-xs text-slate-600">-</span>
          )}
        </td>
        <td className="py-3 text-right text-slate-300">{formatNumber(user.follower_count)}</td>
        <td className="py-3 text-right">
          <Badge color={HIGH_VALUE_COLORS[user.high_value_band] ?? 'gray'}>{Math.round(user.high_value_score)}</Badge>
        </td>
        <td className="py-3 text-right print:hidden">
          {expanded ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
        </td>
      </tr>

      {expanded && (
        <tr>
          <td colSpan={7} className="px-4 pb-4 pt-1">
            <div className="bg-slate-900/50 rounded-lg p-4 space-y-4 border border-slate-700/40">
              {user.bio && <p className="text-sm text-slate-300 italic">"{user.bio}"</p>}

              <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
                <ScoreCard label="Engagement" score={user.engagement_frequency_score} icon={<MessageSquare size={14} />} />
                <ScoreCard label="Topic Relevance" score={user.topic_relevance_score} icon={<Target size={14} />} />
                <ScoreCard label="Influence" score={user.conversation_influence_score} icon={<TrendingUp size={14} />} />
                <ScoreCard label="Conversion" score={user.conversion_likelihood_score} icon={<Star size={14} />} />
              </div>

              <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                <span>User ID: <span className="text-slate-300">{user.user_id || user.platform_user_id}</span></span>
                <span>Joined: <span className="text-slate-300">{formatDate(user.date_joined_twitter)}</span></span>
                <span>Posts: <span className="text-slate-300">{formatNumber(user.tweet_count)}</span></span>
                <span>Following: <span className="text-slate-300">{formatNumber(user.following_count)}</span></span>
              </div>

              {user.hybrid_signals.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">High-Value Signals</p>
                  <div className="flex flex-wrap gap-2">
                    {user.hybrid_signals.map((signal) => <Badge key={signal} color="blue">{signal}</Badge>)}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <div className="space-y-3">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Public Contact Signals</p>
                  <ContactSignals user={user} />
                </div>

                <div className="space-y-3">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Actionable Insight</p>
                  <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/30 space-y-2">
                    {user.recommended_angle && (
                      <p className="text-sm text-slate-200">
                        <span className="text-slate-400">Recommended angle:</span> {user.recommended_angle}
                      </p>
                    )}
                    {user.actionable_insights.length > 0 && (
                      <ul className="space-y-1">
                        {user.actionable_insights.map((insight) => <li key={insight} className="text-sm text-slate-300">- {insight}</li>)}
                      </ul>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 print:hidden">
                <ManualListEditor
                  label="Followers List"
                  helper="Paste one handle per line or use commas. This is the manual column you asked for."
                  value={manualDraft.followersText}
                  onChange={(value) => onManualDraftChange({ followersText: value })}
                />
                <ManualListEditor
                  label="Following List"
                  helper="Used to find shared followed accounts and micro-influencer overlap."
                  value={manualDraft.followingText}
                  onChange={(value) => onManualDraftChange({ followingText: value })}
                />
                <ManualNotesEditor value={manualDraft.notes} onChange={(value) => onManualDraftChange({ notes: value })} />
              </div>

              <div className="flex items-center justify-between gap-4 flex-wrap print:hidden">
                <div className="text-xs text-slate-500">{user.manual_followers_note}</div>
                <Button variant="secondary" size="sm" onClick={onSaveManual} loading={manualSaving}>
                  <Save size={14} />
                  Save Manual Enrichment
                </Button>
              </div>

              {(user.manual_followers_list.length > 0 || user.manual_following_list.length > 0 || user.manual_notes) && (
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                  <StoredManualBlock title="Stored Followers List" values={user.manual_followers_list} />
                  <StoredManualBlock title="Stored Following List" values={user.manual_following_list} />
                  <StoredNotesBlock notes={user.manual_notes} />
                </div>
              )}

              <div className="space-y-2">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Latest Public Tweets</p>
                {displayTweets.length > 0 ? (
                  displayTweets.slice(0, 10).map((tweet) => <TweetCard key={tweet.tweet_id} tweet={tweet} />)
                ) : (
                  <p className="text-sm text-slate-500">No recent tweets available.</p>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

export function SharedFollowingRow({
  candidate,
  selected,
  onToggle,
}: {
  candidate: SharedFollowingCandidate
  selected: boolean
  onToggle: () => void
}) {
  return (
    <tr>
      <td className="py-3 pr-2">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          className="rounded border-slate-600 bg-slate-700 text-brand-600 focus:ring-brand-500"
        />
      </td>
      <td className="py-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-slate-200">@{candidate.username}</span>
            {candidate.high_value_band && <Badge color={HIGH_VALUE_COLORS[candidate.high_value_band] ?? 'gray'}>{candidate.high_value_band}</Badge>}
            {candidate.discovered_user_index !== null && <Badge color="blue">In Discovery List</Badge>}
          </div>
          <p className="text-xs text-slate-500">
            {candidate.display_name || 'Unknown display name'}
            {candidate.user_type ? ` | ${candidate.user_type}` : ''}
          </p>
          <p className="text-xs text-slate-500">
            Followed by: {candidate.followed_by_users.map((handle) => `@${handle}`).join(', ')}
          </p>
        </div>
      </td>
      <td className="py-3 text-right text-slate-300">{candidate.overlap_count}</td>
      <td className="py-3 text-right text-slate-300">{formatNumber(candidate.follower_count)}</td>
      <td className="py-3 text-right">
        <Badge color={candidate.micro_influencer_fit_score >= 70 ? 'green' : candidate.micro_influencer_fit_score >= 55 ? 'blue' : 'yellow'}>
          {Math.round(candidate.micro_influencer_fit_score)}
        </Badge>
      </td>
      <td className="py-3">
        <ul className="space-y-1">
          {candidate.reasons.map((reason) => <li key={reason} className="text-xs text-slate-400">- {reason}</li>)}
        </ul>
      </td>
    </tr>
  )
}

function ScoreCard({ label, score, icon }: { label: string; score: number; icon: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-700/50 bg-slate-800/50 p-3">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span className="flex items-center gap-1.5">{icon}{label}</span>
        <span>{Math.round(score)}</span>
      </div>
      <div className="mt-3 h-2 rounded-full bg-slate-700">
        <div className="h-2 rounded-full bg-gradient-to-r from-sky-500 to-emerald-400" style={{ width: `${Math.max(6, Math.min(score, 100))}%` }} />
      </div>
    </div>
  )
}

function ContactSignals({ user }: { user: DiscoveredUser }) {
  const { emails, phone_numbers, social_handles, urls } = user.public_contact_info
  const hasSignals = emails.length || phone_numbers.length || social_handles.length || urls.length

  if (!hasSignals) {
    return (
      <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/30">
        <p className="text-sm text-slate-500">No email, phone number, URL, or alternate handle found in bio.</p>
      </div>
    )
  }

  return (
    <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/30 space-y-2">
      {emails.length > 0 && <SignalRow icon={<Mail size={13} className="text-slate-500" />} values={emails} color="green" />}
      {phone_numbers.length > 0 && <SignalRow icon={<Phone size={13} className="text-slate-500" />} values={phone_numbers} color="yellow" />}
      {social_handles.length > 0 && <SignalRow icon={<AtSign size={13} className="text-slate-500" />} values={social_handles} color="blue" />}
      {urls.length > 0 && <SignalRow icon={<Link2 size={13} className="text-slate-500" />} values={urls.map((url) => truncate(url, 40))} color="gray" />}
    </div>
  )
}

function SignalRow({
  icon,
  values,
  color,
}: {
  icon: ReactNode
  values: string[]
  color: 'green' | 'yellow' | 'blue' | 'gray'
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {icon}
      {values.map((value) => <Badge key={value} color={color}>{value}</Badge>)}
    </div>
  )
}

function ManualListEditor({
  label,
  helper,
  value,
  onChange,
}: {
  label: string
  helper: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{label}</p>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={7}
        className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
        placeholder="@handle_one&#10;@handle_two"
      />
      <p className="text-xs text-slate-500">{helper}</p>
    </div>
  )
}

function ManualNotesEditor({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Manual Notes</p>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={7}
        className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20"
        placeholder="Paste any manual context, follower observations, or shortlist notes here."
      />
      <p className="text-xs text-slate-500">Useful for manual shortlist reasoning before export or print.</p>
    </div>
  )
}

function StoredManualBlock({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</p>
      <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/30">
        {values.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {values.map((value) => <Badge key={value} color="gray">{value}</Badge>)}
          </div>
        ) : (
          <p className="text-sm text-slate-500">No entries stored.</p>
        )}
      </div>
    </div>
  )
}

function StoredNotesBlock({ notes }: { notes: string | null }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Stored Notes</p>
      <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/30 min-h-[120px]">
        <p className="text-sm text-slate-300 whitespace-pre-wrap">{notes || 'No notes stored.'}</p>
      </div>
    </div>
  )
}

function TweetCard({ tweet }: { tweet: DiscoveredTweet }) {
  return (
    <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/30">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {tweet.post_type && <Badge color="gray">{tweet.post_type}</Badge>}
          {tweet.created_at && (
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <Calendar size={10} />
              {new Date(tweet.created_at).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>
      <p className="text-sm text-slate-200 leading-relaxed mt-2">{tweet.content}</p>
      <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
        <span>Likes {tweet.likes}</span>
        <span>Retweets {tweet.retweets}</span>
        <span>Replies {tweet.replies}</span>
      </div>
    </div>
  )
}

function getDisplayTweets(user: DiscoveredUser): DiscoveredTweet[] {
  return user.last_10_tweets.length > 0 ? user.last_10_tweets : user.matching_tweets
}
