import { NavLink, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Network,
  Search,
  Settings,
  LogOut,
  Zap,
  Megaphone,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { useAuthStore } from '../../store/authStore'
import { NotificationBell } from './NotificationBell'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: BarChart3 },
  { to: '/explorer', label: 'Audience Explorer', icon: Search },
  { to: '/clusters', label: 'Clusters', icon: Network },
  { to: '/campaigns', label: 'Campaigns', icon: Megaphone },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar() {
  const logout = useAuthStore((s) => s.logout)
  const account = useAuthStore((s) => s.account)
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <aside className="flex flex-col w-60 min-h-screen bg-slate-900 border-r border-slate-700/60">
      {/* Logo + notification bell */}
      <div className="flex items-center justify-between px-5 py-5 border-b border-slate-700/60">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-brand-600">
            <Zap size={16} className="text-white" />
          </div>
          <span className="font-bold text-slate-100 tracking-tight text-lg">Meruem</span>
        </div>
        <NotificationBell />
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-brand-600/20 text-brand-400'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100',
              )
            }
          >
            <Icon size={17} />
            {label}
          </NavLink>
        ))}
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
