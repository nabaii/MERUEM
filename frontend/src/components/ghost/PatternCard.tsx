import type { ReactNode } from 'react'
import { Music, Type, Scissors, Mic, Tag } from 'lucide-react'
import type { PatternCard as PatternCardType } from '../../api/ghostVirality'
import { Badge } from '../ui/Badge'
import { Card, CardHeader, CardTitle } from '../ui/Card'

interface Props {
  card: PatternCardType
}

export function PatternCard({ card }: Props) {
  return (
    <Card className="border-pink-500/20 bg-pink-950/5">
      <CardHeader>
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-pink-900/30 p-2">
            <Tag size={15} className="text-pink-400" />
          </div>
          <div>
            <CardTitle>Pattern Card</CardTitle>
            {card.hook_archetype && (
              <p className="text-xs text-pink-400 mt-0.5">{card.hook_archetype}</p>
            )}
          </div>
        </div>
      </CardHeader>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Hook */}
        <div className="rounded-lg bg-slate-700/40 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Scissors size={14} className="text-cyan-400" />
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">Hook</span>
          </div>
          <div className="space-y-1.5 text-sm">
            <Row label="Duration" value={
              card.hook_duration_seconds != null
                ? `${card.hook_duration_seconds.toFixed(1)}s`
                : null
            } />
            <Row label="Scene cuts" value={card.scene_cut_count?.toString() ?? null} />
          </div>
        </div>

        {/* Audio */}
        <div className="rounded-lg bg-slate-700/40 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Music size={14} className="text-purple-400" />
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">Audio</span>
          </div>
          <div className="space-y-1.5 text-sm">
            <Row label="Type" value={
              card.audio_type ? (
                <Badge color={card.audio_type === 'trending' ? 'purple' : card.audio_type === 'original' ? 'green' : 'gray'}>
                  {card.audio_type}
                </Badge>
              ) : null
            } />
            {card.audio_name && <Row label="Track" value={card.audio_name} />}
          </div>
        </div>

        {/* Transcript */}
        {card.transcript_snippet && (
          <div className="rounded-lg bg-slate-700/40 p-4 sm:col-span-2">
            <div className="flex items-center gap-2 mb-3">
              <Mic size={14} className="text-yellow-400" />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">
                Transcript
                {card.transcript_language && (
                  <span className="ml-2 normal-case text-slate-500">({card.transcript_language})</span>
                )}
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed line-clamp-4">
              {card.transcript_snippet}
            </p>
          </div>
        )}

        {/* On-screen text */}
        {card.visual_text && (
          <div className="rounded-lg bg-slate-700/40 p-4 sm:col-span-2">
            <div className="flex items-center gap-2 mb-3">
              <Type size={14} className="text-blue-400" />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">On-screen text</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed line-clamp-3">
              {card.visual_text}
            </p>
          </div>
        )}
      </div>
    </Card>
  )
}

function Row({ label, value }: { label: string; value: ReactNode | null }) {
  if (value == null) return null
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-slate-500 text-xs">{label}</span>
      <span className="text-slate-200 text-xs font-medium">{value}</span>
    </div>
  )
}
