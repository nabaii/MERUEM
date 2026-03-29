import type { Interest } from '../../api/profiles'
import { TOPIC_COLORS } from '../../lib/utils'

interface Props {
  interests: Interest[]
}

export function InterestBars({ interests }: Props) {
  if (!interests.length) {
    return <p className="text-sm text-slate-500">No interests classified yet.</p>
  }

  return (
    <ul className="space-y-2.5">
      {interests.map((i) => (
        <li key={i.topic}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-slate-300 capitalize">{i.topic}</span>
            <span className="text-xs text-slate-500">{Math.round(i.confidence * 100)}%</span>
          </div>
          <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${i.confidence * 100}%`,
                backgroundColor: TOPIC_COLORS[i.topic] ?? '#3b82f6',
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
