import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Account } from '../api/auth'

interface AuthState {
  token: string | null
  account: Account | null
  login: (token: string, account: Account) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      account: null,
      login: (token, account) => {
        localStorage.setItem('meruem_token', token)
        set({ token, account })
      },
      logout: () => {
        localStorage.removeItem('meruem_token')
        set({ token: null, account: null })
      },
    }),
    { name: 'meruem-auth', partialize: (s) => ({ token: s.token, account: s.account }) }
  )
)
