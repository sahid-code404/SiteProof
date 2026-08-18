import type { InspectionPriority, InspectionStatus } from '../lib/api'

export function StatusBadge({ value }: { value: InspectionStatus | InspectionPriority }) {
  return <span className={`badge badge-${value.toLowerCase()}`}>{value.replace('_', ' ')}</span>
}
