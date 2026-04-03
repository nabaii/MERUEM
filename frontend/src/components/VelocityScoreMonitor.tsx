import { Card } from './ui/Card'
import { Activity, Zap } from 'lucide-react'

// Dummy data representing active monitored videos
const MOCK_VIDEOS = [
  { id: 1, title: 'Summer Workout Routine', time: '14m ago', vScore: 24, trajectory: 'up', status: 'monitoring' },
  { id: 2, title: 'Nike Shoes Review', time: '41m ago', vScore: 52, trajectory: 'burst', status: 'breakout' },
  { id: 3, title: 'Healthy Meal Prep', time: '55m ago', vScore: 12, trajectory: 'flat', status: 'monitoring' },
]

export function VelocityScoreMonitor() {
  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 bg-slate-900 border-slate-800">
          <div className="flex items-center space-x-3 text-cyan-400 mb-2">
            <Activity className="h-5 w-5" />
            <h3 className="font-medium">Active Monitors</h3>
          </div>
          <p className="text-3xl font-bold text-slate-100">3</p>
          <p className="text-xs text-slate-500 mt-1">Videos in initial 60m pool</p>
        </Card>
        
        <Card className="p-4 bg-slate-900 border-slate-800">
          <div className="flex items-center space-x-3 text-emerald-400 mb-2">
            <Zap className="h-5 w-5" />
            <h3 className="font-medium">Recent Breakouts</h3>
          </div>
          <p className="text-3xl font-bold text-slate-100">1</p>
          <p className="text-xs text-slate-500 mt-1">Crossed V=50 threshold</p>
        </Card>
        
        <Card className="p-4 bg-slate-900 border-slate-800 opacity-50 relative overflow-hidden">
          <div className="flex items-center space-x-3 text-amber-400 mb-2">
            <span className="h-5 w-5 rounded-full border-2 border-amber-400/50 flex items-center justify-center text-[10px]">💰</span>
            <h3 className="font-medium">Auto-Boosts</h3>
          </div>
          <p className="text-3xl font-bold text-slate-100">0</p>
          <p className="text-xs text-slate-500 mt-1">Spark Ads Triggered</p>
          <div className="absolute top-2 right-2 px-2 py-0.5 bg-amber-500/20 text-amber-400 text-[10px] rounded border border-amber-500/30">
            Sprint 3
          </div>
        </Card>
      </div>

      {/* Monitor Table */}
      <Card className="bg-slate-900 border-slate-800 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-slate-100">Real-Time Trajectory</h2>
          <span className="flex items-center px-2 py-1 bg-emerald-500/10 text-emerald-400 text-xs rounded border border-emerald-500/20 font-medium">
             <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-pulse"></span>
             Live Sync
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-400 uppercase bg-slate-800/50">
              <tr>
                <th className="px-6 py-3">Video</th>
                <th className="px-6 py-3">Time in Pool</th>
                <th className="px-6 py-3">V Score</th>
                <th className="px-6 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_VIDEOS.map((video) => (
                <tr key={video.id} className="border-b border-slate-800 hover:bg-slate-800/30">
                  <td className="px-6 py-4 font-medium text-slate-200">
                    {video.title}
                  </td>
                  <td className="px-6 py-4 text-slate-400">
                    {video.time}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center">
                      <span className={`font-bold mr-2 ${video.vScore >= 50 ? 'text-amber-400' : 'text-slate-200'}`}>
                        {video.vScore}
                      </span>
                      {/* V Score Bar */}
                      <div className="w-24 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                         <div 
                           className={`h-1.5 rounded-full ${video.vScore >= 50 ? 'bg-amber-400' : 'bg-cyan-500'}`} 
                           style={{ width: `${Math.min(100, (video.vScore / 50) * 100)}%` }}></div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {video.status === 'breakout' ? (
                      <span className="px-2 py-1 text-xs font-medium rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
                        Threshold Met
                      </span>
                    ) : (
                      <span className="px-2 py-1 text-xs font-medium rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                        Tracking
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
