import type { InspectionPriority, InspectionStatus } from '../lib/api'

function label(value: InspectionStatus | InspectionPriority) {
  const words = value.toLowerCase().replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export function StatusBadge({ value }: { value: InspectionStatus | InspectionPriority }) {
  return <span className={`badge badge-${value.toLowerCase()}`}>{label(value)}</span>
}
