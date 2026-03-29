import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import type { Cluster } from '../../api/clusters'

interface Props {
  clusters: Cluster[]
}

const COLORS = [
  '#3b82f6', '#8b5cf6', '#10b981', '#f59e0b',
  '#ef4444', '#ec4899', '#06b6d4', '#84cc16',
]

export function ClusterBubbleChart({ clusters }: Props) {
  const data = clusters.map((c, i) => ({
    x: i + 1,
    y: c.member_count,
    z: Math.sqrt(c.member_count) * 4,
    name: c.label ?? `Cluster ${c.id}`,
  }))

  return (
    <ResponsiveContainer width="100%" height={240}>
      <ScatterChart>
        <XAxis dataKey="x" hide />
        <YAxis dataKey="y" name="Members" tick={{ fill: '#94a3b8', fontSize: 11 }} />
        <Tooltip
          cursor={false}
          contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
          labelStyle={{ color: '#f1f5f9' }}
          formatter={(val: number, name: string) =>
            name === 'y' ? [val.toLocaleString(), 'Members'] : [val, name]
          }
        />
        <Scatter data={data} isAnimationActive={false}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} fillOpacity={0.85} />
          ))}
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  )
}
