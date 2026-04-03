import { useState } from 'react'
import { MonitorPlay, FileCheck2 } from 'lucide-react'
import { TikTokAuditor } from '../components/TikTokAuditor'
import { VelocityScoreMonitor } from '../components/VelocityScoreMonitor'

export function TikTokPage() {
  const [activeTab, setActiveTab] = useState<'monitor' | 'auditor'>('monitor')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">TikTok Intelligence</h1>
        <p className="mt-1 text-sm text-slate-400">Velocity Score tracking and Legibility Auditor.</p>
      </div>

      <div className="flex space-x-1 border-b border-slate-700 pb-px">
        <button
          onClick={() => setActiveTab('monitor')}
          className={`flex items-center space-x-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'monitor'
              ? 'border-cyan-400 text-cyan-400'
              : 'border-transparent text-slate-400 hover:text-slate-300 hover:border-slate-600'
          }`}
        >
          <MonitorPlay size={16} />
          <span>Velocity Monitor</span>
        </button>
        <button
          onClick={() => setActiveTab('auditor')}
          className={`flex items-center space-x-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'auditor'
              ? 'border-cyan-400 text-cyan-400'
              : 'border-transparent text-slate-400 hover:text-slate-300 hover:border-slate-600'
          }`}
        >
          <FileCheck2 size={16} />
          <span>Legibility Auditor</span>
        </button>
      </div>

      <div className="pt-4">
        {activeTab === 'monitor' ? <VelocityScoreMonitor /> : <TikTokAuditor />}
      </div>
    </div>
  )
}
