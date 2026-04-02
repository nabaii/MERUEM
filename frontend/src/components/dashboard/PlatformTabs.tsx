import type { ReactNode } from 'react'

import { cn } from '../../lib/utils'

type Platform = 'overview' | 'twitter' | 'instagram' | 'tiktok'

interface Tab {
  id: Platform
  label: string
  icon: ReactNode
  comingSoon?: boolean
}

interface Props {
  activeTab: Platform
  onChange: (tab: Platform) => void
}

function OverviewIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={cn('h-5 w-5', className)}>
      <path d="M3 13h8V3H3zm0 8h8v-6H3zm10 0h8V11h-8zm0-18v6h8V3z" />
    </svg>
  )
}

function TwitterIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={cn('h-5 w-5', className)}>
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  )
}

function InstagramIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={cn('h-5 w-5', className)}>
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
    </svg>
  )
}

function TikTokIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={cn('h-5 w-5', className)}>
      <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1v-3.5a6.37 6.37 0 00-.79-.05A6.34 6.34 0 003.15 15.2a6.34 6.34 0 0010.86 4.47v-7.15a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-.81.05h-.38z" />
    </svg>
  )
}

const tabs: Tab[] = [
  {
    id: 'overview',
    label: 'Overview',
    icon: <OverviewIcon />,
  },
  {
    id: 'twitter',
    label: 'Twitter / X',
    icon: <TwitterIcon />,
  },
  {
    id: 'instagram',
    label: 'Instagram',
    icon: <InstagramIcon />,
    comingSoon: true,
  },
  {
    id: 'tiktok',
    label: 'TikTok',
    icon: <TikTokIcon />,
    comingSoon: true,
  },
]

export function PlatformTabs({ activeTab, onChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-1 rounded-xl border border-slate-700/50 bg-slate-800/60 p-1.5 backdrop-blur-sm">
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id

        return (
          <button
            key={tab.id}
            onClick={() => !tab.comingSoon && onChange(tab.id)}
            disabled={tab.comingSoon}
            className={cn(
              'relative flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all duration-300 ease-out',
              isActive
                ? 'bg-slate-700 text-white shadow-lg shadow-slate-900/50'
                : 'text-slate-400 hover:bg-slate-700/40 hover:text-slate-200',
              tab.comingSoon && 'cursor-not-allowed opacity-40',
            )}
          >
            <span
              className={cn(
                'transition-colors duration-300',
                isActive && tab.id === 'overview' && 'text-brand-400',
                isActive && tab.id === 'twitter' && 'text-sky-400',
                isActive && tab.id === 'instagram' && 'text-pink-400',
                isActive && tab.id === 'tiktok' && 'text-cyan-400',
              )}
            >
              {tab.icon}
            </span>
            <span>{tab.label}</span>
            {tab.comingSoon && (
              <span className="ml-1 rounded bg-slate-600/50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                Soon
              </span>
            )}
            {isActive && (
              <span
                className={cn(
                  'absolute bottom-0 left-1/2 h-0.5 w-8 -translate-x-1/2 rounded-full',
                  tab.id === 'overview' && 'bg-brand-400',
                  tab.id === 'twitter' && 'bg-sky-400',
                  tab.id === 'instagram' && 'bg-gradient-to-r from-purple-500 to-pink-500',
                  tab.id === 'tiktok' && 'bg-cyan-400',
                )}
              />
            )}
          </button>
        )
      })}
    </div>
  )
}

export type { Platform }
