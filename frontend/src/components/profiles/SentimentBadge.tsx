import { sentimentLabel } from '../../lib/utils'
import { Badge } from '../ui/Badge'

export function SentimentBadge({ score }: { score: number | null | undefined }) {
  const label = sentimentLabel(score)
  return (
    <Badge color={label === 'positive' ? 'green' : label === 'negative' ? 'red' : 'gray'}>
      {label}
    </Badge>
  )
}
