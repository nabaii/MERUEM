import { Link } from 'react-router-dom'
import { Users, MapPin, Twitter, Instagram, Facebook } from 'lucide-react'
import type { Profile } from '../../api/profiles'
import { formatNumber } from '../../lib/utils'
import { Badge } from '../ui/Badge'

interface Props {
  profile: Profile
}

const PLATFORM_ICONS: Record<string, React.ReactNode> = {
  twitter: <Twitter size={13} className="text-[#1DA1F2]" />,
  instagram: <Instagram size={13} className="text-[#E1306C]" />,
  facebook: <Facebook size={13} className="text-[#1877F2]" />,
}

export function ProfileCard({ profile }: Props) {
  return (
    <Link
      to={`/profiles/${profile.id}`}
      className="block bg-slate-800 border border-slate-700 rounded-xl p-4 hover:border-brand-600/60 hover:bg-slate-750 transition-colors"
    >
      <div className="flex items-start gap-3">
        {profile.profile_image_url ? (
          <img
            src={profile.profile_image_url}
            alt={profile.display_name ?? profile.username ?? ''}
            className="w-10 h-10 rounded-full object-cover flex-shrink-0"
          />
        ) : (
          <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0">
            <Users size={18} className="text-slate-500" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            {PLATFORM_ICONS[profile.platform]}
            <p className="text-sm font-semibold text-slate-100 truncate">
              {profile.display_name ?? profile.username ?? profile.platform_user_id}
            </p>
          </div>
          {profile.username && (
            <p className="text-xs text-slate-500 truncate">@{profile.username}</p>
          )}
        </div>
      </div>

      {profile.bio && (
        <p className="mt-2.5 text-xs text-slate-400 line-clamp-2">{profile.bio}</p>
      )}

      <div className="mt-3 flex items-center gap-3 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <Users size={11} />
          {formatNumber(profile.follower_count)} followers
        </span>
        {profile.location_inferred && (
          <span className="flex items-center gap-1 truncate">
            <MapPin size={11} />
            {profile.location_inferred}
          </span>
        )}
        {profile.cluster_id != null && (
          <Badge color="blue">Cluster {profile.cluster_id}</Badge>
        )}
      </div>
    </Link>
  )
}
