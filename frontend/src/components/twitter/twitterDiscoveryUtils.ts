import type { DiscoveryResponse, DiscoveredUser, SharedFollowingsResponse } from '../../api/discovery'

export type ManualDraft = {
  followersText: string
  followingText: string
  notes: string
}

export const HIGH_VALUE_COLORS: Record<string, 'green' | 'blue' | 'yellow' | 'gray'> = {
  'Very High': 'green',
  High: 'blue',
  Medium: 'yellow',
  Low: 'gray',
}

export function createManualDraft(user?: DiscoveredUser | null): ManualDraft {
  return {
    followersText: (user?.manual_followers_list ?? []).join('\n'),
    followingText: (user?.manual_following_list ?? []).join('\n'),
    notes: user?.manual_notes ?? '',
  }
}

export function parseManualList(text: string): string[] {
  const seen = new Set<string>()
  const values: string[] = []

  text
    .split(/[\n,;|]+/)
    .map((value) => normalizeHandle(value))
    .forEach((value) => {
      if (!value || seen.has(value)) return
      seen.add(value)
      values.push(value)
    })

  return values
}

export function normalizeHandle(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\/(x|twitter)\.com\//, '')
    .replace(/^@/, '')
    .replace(/\/+$/, '')
}

export function formatDate(value: string | null) {
  if (!value) return 'Unknown'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString()
}

export function truncate(value: string, maxLength: number) {
  if (value.length <= maxLength) return value
  return `${value.slice(0, maxLength - 3)}...`
}

export function printDiscoveryReport(
  results: DiscoveryResponse,
  sharedFollowings: SharedFollowingsResponse | null,
  selectedMicroInfluencers: Set<string>,
) {
  const printWindow = window.open('', '_blank', 'width=1200,height=800')
  if (!printWindow) {
    throw new Error('Unable to open a print window')
  }

  const selectedCandidates =
    sharedFollowings?.candidates.filter((candidate) => selectedMicroInfluencers.has(candidate.username)) ?? []

  const reportRows = results.users
    .map((user) => {
      const selected = selectedMicroInfluencers.has(user.username.toLowerCase()) ? 'Yes' : 'No'
      return `
        <tr>
          <td>@${escapeHtml(user.username)}</td>
          <td>${escapeHtml(user.display_name || '')}</td>
          <td>${escapeHtml(user.user_type || '')}</td>
          <td>${Math.round(user.high_value_score)}</td>
          <td>${Math.round(user.topic_relevance_score)}</td>
          <td>${Math.round(user.conversion_likelihood_score)}</td>
          <td>${escapeHtml(user.manual_followers_list.join(', '))}</td>
          <td>${escapeHtml(user.manual_following_list.join(', '))}</td>
          <td>${escapeHtml(user.manual_notes || '')}</td>
          <td>${selected}</td>
        </tr>
      `
    })
    .join('')

  const selectedCandidatesMarkup =
    selectedCandidates.length > 0
      ? `
      <h2>Selected Micro-Influencers</h2>
      <table>
        <thead>
          <tr>
            <th>Username</th>
            <th>Overlap</th>
            <th>Followers</th>
            <th>Fit Score</th>
            <th>Reasons</th>
          </tr>
        </thead>
        <tbody>
          ${selectedCandidates
            .map(
              (candidate) => `
            <tr>
              <td>@${escapeHtml(candidate.username)}</td>
              <td>${candidate.overlap_count}</td>
              <td>${candidate.follower_count ?? ''}</td>
              <td>${Math.round(candidate.micro_influencer_fit_score)}</td>
              <td>${escapeHtml(candidate.reasons.join(' | '))}</td>
            </tr>
          `,
            )
            .join('')}
        </tbody>
      </table>
    `
      : ''

  printWindow.document.write(`
    <html>
      <head>
        <title>Meruem Discovery Report</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 24px; color: #111827; }
          h1, h2 { margin: 0 0 12px; }
          p { margin: 0 0 16px; }
          table { width: 100%; border-collapse: collapse; margin-bottom: 24px; }
          th, td { border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; font-size: 12px; }
          th { background: #f3f4f6; }
        </style>
      </head>
      <body>
        <h1>Meruem Twitter Discovery Report</h1>
        <p>Profiled users: ${results.profiled_users_count} | High-value users: ${results.high_value_users_found} | Location: ${escapeHtml(results.location)}</p>
        <table>
          <thead>
            <tr>
              <th>Username</th>
              <th>Display Name</th>
              <th>User Type</th>
              <th>High-Value Score</th>
              <th>Topic Score</th>
              <th>Conversion Score</th>
              <th>Followers List</th>
              <th>Following List</th>
              <th>Manual Notes</th>
              <th>Selected as Micro-Influencer</th>
            </tr>
          </thead>
          <tbody>${reportRows}</tbody>
        </table>
        ${selectedCandidatesMarkup}
      </body>
    </html>
  `)
  printWindow.document.close()
  printWindow.focus()
  printWindow.print()
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
