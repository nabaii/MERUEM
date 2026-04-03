import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  BarChart3,
  Network,
  Search,
  Settings,
  LogOut,
  Zap,
  Megaphone,
  DatabaseZap,
  Ghost,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useAuthStore } from '../../store/authStore'
import { NotificationBell } from './NotificationBell'

// --- SVG platform icons ---

function TwitterIcon({ size = 17 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: size, height: size }}>
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  )
}

function InstagramIcon({ size = 17 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: size, height: size }}>
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
    </svg>
  )
}

function TikTokIcon({ size = 17 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: size, height: size }}>
      <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1v-3.5a6.37 6.37 0 00-.79-.05A6.34 6.34 0 003.15 15.2a6.34 6.34 0 0010.86 4.47v-7.15a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-.81.05h-.38z" />
    </svg>
  )
}

// --- Nav structure ---

// Top section: core analytics
const CORE_NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: BarChart3 },
  { to: '/explorer', label: 'Audience Explorer', icon: Search },
  { to: '/clusters', label: 'Clusters', icon: Network },
  { to: '/campaigns', label: 'Campaigns', icon: Megaphone },
]

// Platform section
const PLATFORM_NAV = [
  { to: '/twitter', label: 'Twitter / X', renderIcon: () => <TwitterIcon /> },
  { to: '/instagram', label: 'Instagram', renderIcon: () => <InstagramIcon /> },
  { to: '/tiktok', label: 'TikTok', renderIcon: () => <TikTokIcon /> },
]

// Instagram sub-nav items
const INSTAGRAM_SUB_NAV = [
  { to: '/ghost-virality', label: 'Ghost Virality', icon: Ghost },
]

// Bottom section
const BOTTOM_NAV = [
  { to: '/import', label: 'Import Data', icon: DatabaseZap },
  { to: '/settings', label: 'Settings', icon: Settings },
]

const linkBase =
  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors'
const activeClass = 'bg-brand-600/20 text-brand-400'
const inactiveClass = 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'

export function Sidebar() {
  const logout = useAuthStore((s) => s.logout)
  const account = useAuthStore((s) => s.account)
  const navigate = useNavigate()
  const location = useLocation()

  const instagramActive =
    location.pathname === '/instagram' ||
    location.pathname.startsWith('/ghost-virality')

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <aside className="flex flex-col w-60 min-h-screen bg-slate-900 border-r border-slate-700/60">
      {/* Logo */}
      <div className="flex items-center justify-between px-5 py-5 border-b border-slate-700/60">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-brand-600">
            <Zap size={16} className="text-white" />
          </div>
          <span className="font-bold text-slate-100 tracking-tight text-lg">Meruem</span>
        </div>
        <NotificationBell />
      </div>

      <nav className="flex-1 px-3 py-4 space-y-5 overflow-y-auto">
        {/* Core */}
        <div className="space-y-0.5">
          {CORE_NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => cn(linkBase, isActive ? activeClass : inactiveClass)}
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
        </div>

        {/* Platforms */}
        <div>
          <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
            Platforms
          </p>
          <div className="space-y-0.5">
            {PLATFORM_NAV.map(({ to, label, renderIcon }) => {
              const isInstagram = to === '/instagram'
              const isActive = isInstagram ? instagramActive : location.pathname === to

              return (
                <div key={to}>
                  <NavLink
                    to={to}
                    className={cn(linkBase, isActive ? activeClass : inactiveClass)}
                  >
                    {renderIcon()}
                    {label}
                  </NavLink>

                  {/* Instagram sub-nav — always visible when instagram or child is active */}
                  {isInstagram && instagramActive && (
                    <div className="mt-0.5 ml-3 pl-4 border-l border-slate-700/60 space-y-0.5">
                      {INSTAGRAM_SUB_NAV.map(({ to: subTo, label: subLabel, icon: SubIcon }) => (
                        <NavLink
                          key={subTo}
                          to={subTo}
                          className={({ isActive: subActive }) =>
                            cn(
                              'flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
                              subActive
                                ? 'text-pink-400 bg-pink-900/20'
                                : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300',
                            )
                          }
                        >
                          <SubIcon size={14} />
                          {subLabel}
                        </NavLink>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Data */}
        <div>
          <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
            Data
          </p>
          <div className="space-y-0.5">
            {BOTTOM_NAV.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) => cn(linkBase, isActive ? activeClass : inactiveClass)}
              >
                <Icon size={17} />
                {label}
              </NavLink>
            ))}
          </div>
        </div>
      </nav>

      {/* User footer */}
      <div className="px-3 py-4 border-t border-slate-700/60 space-y-0.5">
        <div className="px-3 py-2">
          <p className="text-xs font-medium text-slate-100 truncate">{account?.full_name ?? account?.email}</p>
          <p className="text-xs text-slate-500 truncate capitalize">{account?.role}</p>
        </div>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition-colors"
        >
          <LogOut size={17} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
