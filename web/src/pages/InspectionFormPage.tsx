import { type FormEvent, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { SiteMap } from '../components/SiteMap'
import { createInspection, getInspection, updateInspection, type InspectionPayload, type InspectionPriority, type InspectionType } from '../lib/api'
import { validateInspectionInput } from '../lib/inspectionValidation'

type FormState = {
  title: string
  description: string
  inspectionType: InspectionType
  priority: InspectionPriority
  latitude: string
  longitude: string
  locationName: string
  locationAddress: string
  radius: string
  deadline: string
  instructions: string
}

const initialState: FormState = {
  title: '', description: '', inspectionType: 'GENERAL', priority: 'MEDIUM',
  latitude: '22.5726', longitude: '88.3639', locationName: '', locationAddress: '', radius: '100',
  deadline: '', instructions: '',
}

function toLocalInput(iso: string): string {
  const date = new Date(iso)
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export function InspectionFormPage() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [form, setForm] = useState<FormState>(initialState)
  const [clientError, setClientError] = useState<string | null>(null)
  const existing = useQuery({ queryKey: ['inspection', id], queryFn: () => getInspection(id!), enabled: editing })

  useEffect(() => {
    if (!existing.data) return
    const item = existing.data
    setForm({
      title: item.title,
      description: item.description ?? '',
      inspectionType: item.inspectionType,
      priority: item.priority,
      latitude: String(item.expectedLatitude),
      longitude: String(item.expectedLongitude),
      locationName: item.locationName ?? '',
      locationAddress: item.locationAddress ?? '',
      radius: String(item.allowedRadiusMeters),
      deadline: toLocalInput(item.deadline),
      instructions: item.instructions ?? '',
    })
  }, [existing.data])

  const mutation = useMutation({
    mutationFn: (payload: InspectionPayload) => editing ? updateInspection(id!, payload) : createInspection(payload),
    onSuccess(data) {
      queryClient.invalidateQueries({ queryKey: ['inspections'] })
      queryClient.invalidateQueries({ queryKey: ['inspection-summary'] })
      queryClient.setQueryData(['inspection', data.id], data)
      navigate(`/inspections/${data.id}`)
    },
  })

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const latitude = Number(form.latitude)
    const longitude = Number(form.longitude)
    const radius = Number(form.radius)
    const validationError = validateInspectionInput({
      title: form.title,
      latitude,
      longitude,
      radius,
      deadline: form.deadline,
    })
    if (validationError) {
      setClientError(validationError)
      return
    }
    setClientError(null)
    mutation.mutate({
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      inspectionType: form.inspectionType,
      priority: form.priority,
      location: {
        latitude, longitude,
        name: form.locationName.trim() || undefined,
        address: form.locationAddress.trim() || undefined,
      },
      allowedRadiusMeters: radius,
      deadline: new Date(form.deadline).toISOString(),
      instructions: form.instructions.trim() || undefined,
    })
  }

  const latitude = Number(form.latitude) || 0
  const longitude = Number(form.longitude) || 0
  const radius = Number(form.radius) || 100

  if (existing.isLoading) return <div className="loading-block">Loading inspection…</div>
  if (existing.isError) return <div className="notice error">{existing.error.message}</div>

  return (
    <>
      <section className="page-heading"><p className="eyebrow">{editing ? 'EDIT INSPECTION' : 'NEW INSPECTION'}</p><h1>{editing ? 'Update field requirements' : 'Create inspection'}</h1><p>Define the task and site precisely. Assignment happens after the inspection is saved.</p></section>
      <form className="form-layout" onSubmit={submit}>
        <section className="form-card"><div className="section-title"><span>01</span><div><h2>Basic information</h2><p>Describe what the inspector needs to verify.</p></div></div>
          <label className="wide">Title<input minLength={3} maxLength={150} value={form.title} onChange={(event) => update('title', event.target.value)} required /></label>
          <label className="wide">Description<textarea rows={4} maxLength={5000} value={form.description} onChange={(event) => update('description', event.target.value)} /></label>
          <div className="field-grid"><label>Inspection type<select value={form.inspectionType} onChange={(event) => update('inspectionType', event.target.value as InspectionType)}>{['ROAD_REPAIR','INFRASTRUCTURE','CONSTRUCTION','UTILITY','GENERAL'].map((item) => <option key={item}>{item}</option>)}</select></label><label>Priority<select value={form.priority} onChange={(event) => update('priority', event.target.value as InspectionPriority)}>{['LOW','MEDIUM','HIGH','CRITICAL'].map((item) => <option key={item}>{item}</option>)}</select></label></div>
        </section>

        <section className="form-card"><div className="section-title"><span>02</span><div><h2>Site</h2><p>Click the map or enter coordinates. OpenStreetMap provides the base map.</p></div></div>
          <SiteMap latitude={latitude} longitude={longitude} radius={radius} editable onChange={(lat, lng) => setForm((current) => ({ ...current, latitude: lat.toFixed(6), longitude: lng.toFixed(6) }))} />
          <div className="field-grid"><label>Latitude<input type="number" step="0.000001" min="-90" max="90" value={form.latitude} onChange={(event) => update('latitude', event.target.value)} required /></label><label>Longitude<input type="number" step="0.000001" min="-180" max="180" value={form.longitude} onChange={(event) => update('longitude', event.target.value)} required /></label></div>
          <div className="field-grid"><label>Location name<input maxLength={200} value={form.locationName} onChange={(event) => update('locationName', event.target.value)} placeholder="Central Avenue" /></label><label>Allowed radius (m)<input type="number" min="10" max="5000" value={form.radius} onChange={(event) => update('radius', event.target.value)} required /></label></div>
          <label className="wide">Address<input maxLength={500} value={form.locationAddress} onChange={(event) => update('locationAddress', event.target.value)} placeholder="Kolkata, West Bengal" /></label>
        </section>

        <section className="form-card"><div className="section-title"><span>03</span><div><h2>Deadline & instructions</h2><p>Browser local time is converted to an ISO timestamp before submission.</p></div></div>
          <label>Deadline<input type="datetime-local" value={form.deadline} onChange={(event) => update('deadline', event.target.value)} required /></label>
          <label className="wide">Inspector instructions<textarea rows={6} maxLength={5000} value={form.instructions} onChange={(event) => update('instructions', event.target.value)} /></label>
        </section>

        {clientError ? <div className="notice error">{clientError}</div> : null}
        {mutation.isError ? <div className="notice error">{mutation.error.message}</div> : null}
        <div className="form-actions"><Link className="button ghost" to={editing ? `/inspections/${id}` : '/inspections'}>Cancel</Link><button className="button primary" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : editing ? 'Save changes' : 'Create inspection'}</button></div>
      </form>
    </>
  )
}
