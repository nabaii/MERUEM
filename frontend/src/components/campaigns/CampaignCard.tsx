import { Link } from 'react-router-dom'
import { Users, Calendar, MoreHorizontal } from 'lucide-react'
import { Campaign } from '../../api/campaigns'
import { cn } from '../../lib/utils'

const STATUS_STYLE: Record<string, string> = {
  draft: 'bg-slate-700 text-slate-300',
  active: 'bg-green-900/60 text-green-400',
  exported: 'bg-blue-900/60 text-blue-400',
  completed: 'bg-purple-900/60 text-purple-400',
}

export function CampaignCard({ campaign }: { campaign: Campaign }) {
  return (
    <Link
      to={`/campaigns/${campaign.id}`}
      className="block bg-slate-800/60 border border-slate-700/60 rounded-xl p-5 hover:border-brand-600/60 hover:bg-slate-800 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-100 truncate">{campaign.name}</h3>
        <span
          className={cn(
            'flex-shrink-0 text-[11px] font-medium px-2 py-0.5 rounded-full capitalize',
            STATUS_STYLE[campaign.status] ?? 'bg-slate-700 text-slate-400',
          )}
        >
          {campaign.status}
        </span>
      </div>

      <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <Users size={12} />
          {campaign.audience_count.toLocaleString()} profiles
        </span>
        <span className="flex items-center gap-1.5">
          <Calendar size={12} />
          {new Date(campaign.created_at).toLocaleDateString()}
        </span>
      </div>
    </Link>
  )
}
