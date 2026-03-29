import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Zap } from 'lucide-react'
import { authApi } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import toast from 'react-hot-toast'

export function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  function handleSkip() {
    login('dev-bypass', { id: 'dev', email: 'dev@meruem.local', full_name: 'Dev User', role: 'admin', is_active: true } as any)
    navigate('/dashboard')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const token = await authApi.login(email, password)
      const account = await (async () => {
        localStorage.setItem('meruem_token', token.access_token)
        return authApi.me()
      })()
      login(token.access_token, account)
      navigate('/dashboard')
    } catch (err: any) {
      toast.error(err.message ?? 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2.5 mb-8">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-brand-600">
            <Zap size={20} className="text-white" />
          </div>
          <span className="text-2xl font-bold text-slate-100 tracking-tight">Meruem</span>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-2xl p-8">
          <h1 className="text-lg font-semibold text-slate-100 mb-1">Sign in</h1>
          <p className="text-sm text-slate-400 mb-6">Audience intelligence platform</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              id="email"
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@brand.com"
              required
              autoFocus
            />
            <Input
              id="password"
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
            <Button type="submit" loading={loading} className="w-full justify-center">
              Sign in
            </Button>
          </form>

          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1 h-px bg-slate-700" />
            <span className="text-xs text-slate-500">or</span>
            <div className="flex-1 h-px bg-slate-700" />
          </div>

          <button
            type="button"
            onClick={handleSkip}
            className="mt-3 w-full text-sm text-slate-400 hover:text-slate-200 transition-colors py-2"
          >
            Skip login (dev)
          </button>

          <p className="mt-2 text-center text-sm text-slate-400">
            No account yet?{' '}
            <Link to="/register" className="text-brand-400 hover:text-brand-300">
              Create one
            </Link>
          </p>
        </div>

        <p className="mt-4 text-center text-xs text-slate-600">
          Meruem © {new Date().getFullYear()}
        </p>
      </div>
    </div>
  )
}
