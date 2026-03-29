import { api } from './client'

export type NotificationType =
  | 'export_ready'
  | 'export_failed'
  | 'campaign_activated'
  | 'campaign_completed'
  | 'system'

export interface AppNotification {
  id: string
  account_id: string
  type: NotificationType
  title: string
  body: string
  is_read: boolean
  data: Record<string, unknown> | null
  created_at: string
}

export interface NotificationListResponse {
  items: AppNotification[]
  total: number
  unread_count: number
}

export const notificationsApi = {
  list: (unreadOnly = false) =>
    api.get<NotificationListResponse>(
      `/notifications${unreadOnly ? '?unread_only=true' : ''}`
    ),

  markRead: (id: string) => api.post<void>(`/notifications/${id}/read`, {}),

  markAllRead: () => api.post<void>('/notifications/read-all', {}),
}
