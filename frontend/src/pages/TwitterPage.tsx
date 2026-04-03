import { TwitterDashboardTab } from '../components/twitter/TwitterDashboardTab'

export function TwitterPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Twitter / X</h1>
        <p className="mt-1 text-sm text-slate-400">Audience discovery and intelligence for Twitter / X.</p>
      </div>
      <TwitterDashboardTab />
    </div>
  )
}
