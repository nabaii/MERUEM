import { api } from './client'

export interface Account {
  id: string
  email: string
  full_name: string | null
  role: 'admin' | 'client'
  is_active: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }),

  register: (email: string, password: string, full_name?: string) =>
    api.post<Account>('/auth/register', { email, password, full_name }),

  me: () => api.get<Account>('/auth/me'),

  generateApiKey: () => api.post<{ api_key: string }>('/auth/api-key'),
}
