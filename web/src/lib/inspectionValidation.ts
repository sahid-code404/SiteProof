export type InspectionValidationInput = {
  title: string
  latitude: number
  longitude: number
  radius: number
  deadline: string
}

export function validateInspectionInput(input: InspectionValidationInput): string | null {
  const titleLength = input.title.trim().length
  if (titleLength < 3 || titleLength > 150) return 'Title must be between 3 and 150 characters.'
  if (!Number.isFinite(input.latitude) || input.latitude < -90 || input.latitude > 90) return 'Latitude must be between -90 and 90.'
  if (!Number.isFinite(input.longitude) || input.longitude < -180 || input.longitude > 180) return 'Longitude must be between -180 and 180.'
  if (!Number.isFinite(input.radius) || input.radius < 10 || input.radius > 5000) return 'Allowed radius must be between 10 and 5000 metres.'
  const deadline = new Date(input.deadline)
  if (Number.isNaN(deadline.getTime()) || deadline.getTime() <= Date.now()) return 'Deadline must be in the future.'
  return null
}
