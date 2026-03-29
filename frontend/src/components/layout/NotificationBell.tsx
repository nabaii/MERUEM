import { useEffect, useRef, useState } from 'react'
import { Bell, Check, CheckCheck } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { notificationsApi, AppNotification } from '../../api/notifications'
import { cn } from '../../lib/utils'
import { formatDistanceToNow } from 'date-fns'

const TYPE_ICON: Record<string, string> = {
  export_ready: '✅',
  export_failed: '❌',
  campaign_activated: '🚀',
  campaign_completed: '🏁',
  system: 'ℹ️',
}

export function NotificationBell() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  const { data } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list(),
    refetchInterval: 30_000,
  })

  const markRead = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })

  const markAll = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const unread = data?.unread_count ?? 0
  const items = data?.items ?? []

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative flex items-center justify-center w-9 h-9 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-slate-100 transition-colors"
        aria-label="Notifications"
      >
        <Bell size={18} />
        {unread > 0 && (
          <span className="absolute top-1 right-1 flex items-center justify-center w-4 h-4 rounded-full bg-brand-600 text-white text-[10px] font-bold leading-none">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-50 w-80 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
            <span className="text-sm font-semibold text-slate-100">Notifications</span>
            {unread > 0 && (
              <button
                onClick={() => markAll.mutate()}
                className="flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300"
              >
                <CheckCheck size={13} />
                Mark all read
              </button>
            )}
          </div>

          {/* List */}
          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-slate-500">No notifications</div>
            ) : (
              items.map((n) => <NotifItem key={n.id} n={n} onRead={() => markRead.mutate(n.id)} />)
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function NotifItem({ n, onRead }: { n: AppNotification; onRead: () => void }) {
  return (
    <div
      className={cn(
        'flex gap-3 px-4 py-3 border-b border-slate-800 last:border-0',
        n.is_read ? 'opacity-60' : 'bg-slate-800/40',
      )}
    >
      <span className="text-lg leading-none mt-0.5">{TYPE_ICON[n.type] ?? 'ℹ️'}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-100 leading-snug">{n.title}</p>
        <p className="text-xs text-slate-400 mt-0.5 leading-snug">{n.body}</p>
        <p className="text-[11px] text-slate-600 mt-1">
          {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
        </p>
      </div>
      {!n.is_read && (
        <button onClick={onRead} className="text-slate-500 hover:text-brand-400 flex-shrink-0 mt-1">
          <Check size={14} />
        </button>
      )}
    </div>
  )
}
