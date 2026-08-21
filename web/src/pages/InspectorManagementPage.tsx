import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createInspector,
  listInspectors,
  resetInspectorPassword,
  updateInspector,
  type InspectorCreatePayload,
} from '../lib/inspectorApi'

type StatusFilter = 'all' | 'active' | 'inactive'

const emptyCreate: InspectorCreatePayload = {
  fullName: '',
  email: '',
  password: '',
  employeeCode: '',
  phone: '',
}

function shortId(id: string) {
  return id.split('-')[0].toUpperCase()
}

function StatIcon({ type }: { type: 'total' | 'active' | 'inactive' | 'id' }) {
  if (type === 'total') return <span className="stat-icon peach">👥</span>
  if (type === 'active') return <span className="stat-icon mint">●</span>
  if (type === 'inactive') return <span className="stat-icon rose">○</span>
  return <span className="stat-icon amber">ID</span>
}

export function InspectorManagementPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [createForm, setCreateForm] = useState<InspectorCreatePayload>(emptyCreate)
  const [confirmCreatePassword, setConfirmCreatePassword] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const activeFilter = statusFilter === 'all' ? undefined : statusFilter === 'active'
  const inspectors = useQuery({
    queryKey: ['inspector-management', search, activeFilter],
    queryFn: () => listInspectors(search, activeFilter),
  })

  const allInspectors = useMemo(() => inspectors.data?.items ?? [], [inspectors.data?.items])
  const selected = useMemo(
    () => allInspectors.find((item) => item.id === selectedId) ?? null,
    [allInspectors, selectedId],
  )

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ['inspector-management'] })
    queryClient.invalidateQueries({ queryKey: ['inspectors'] })
  }

  const createMutation = useMutation({
    mutationFn: createInspector,
    onSuccess: (created) => {
      setCreateForm(emptyCreate)
      setConfirmCreatePassword('')
      setSelectedId(created.id)
      setSuccessMessage(`${created.name} can now sign in to the Android app.`)
      refresh()
    },
  })

  const accountMutation = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => updateInspector(id, { active }),
    onSuccess: (updated) => {
      setSuccessMessage(`${updated.name} is now ${updated.active ? 'active' : 'inactive'}.`)
      refresh()
    },
  })

  const passwordMutation = useMutation({
    mutationFn: ({ id, nextPassword }: { id: string; nextPassword: string }) => resetInspectorPassword(id, nextPassword),
    onSuccess: () => {
      setPassword('')
      setConfirmPassword('')
      setSuccessMessage('Password updated. The previous password no longer works.')
    },
  })

  function submitCreate(event: FormEvent) {
    event.preventDefault()
    if (createForm.password !== confirmCreatePassword) return
    setSuccessMessage(null)
    createMutation.mutate({
      ...createForm,
      fullName: createForm.fullName.trim(),
      email: createForm.email.trim().toLowerCase(),
      employeeCode: createForm.employeeCode?.trim() || undefined,
      phone: createForm.phone?.trim() || undefined,
    })
  }

  function submitPassword(event: FormEvent) {
    event.preventDefault()
    if (!selected || password.length < 8 || password !== confirmPassword) return
    setSuccessMessage(null)
    passwordMutation.mutate({ id: selected.id, nextPassword: password })
  }

  const total = inspectors.data?.totalItems ?? 0
  const active = allInspectors.filter((item) => item.active).length
  const inactive = allInspectors.filter((item) => !item.active).length
  const withId = allInspectors.filter((item) => item.employeeCode).length

  return (
    <div className="page-stack inspector-management-page">
      <header className="page-heading inspector-page-heading entrance-up">
        <div>
          <h1>Inspectors</h1>
          <p>Manage inspectors and their access.</p>
        </div>
        <a className="button primary add-inspector-button" href="#add-inspector"><span aria-hidden="true">＋</span> Add Inspector</a>
      </header>

      {successMessage ? <div className="notice success entrance-up" role="status">{successMessage}</div> : null}

      <section className="inspector-stats" aria-label="Inspector account summary">
        <article className="metric-card inspector-stat-card entrance-up delay-1"><StatIcon type="total"/><div><span>Total Inspectors</span><strong>{total}</strong><small>All accounts</small></div></article>
        <article className="metric-card inspector-stat-card entrance-up delay-2"><StatIcon type="active"/><div><span>Active Inspectors</span><strong>{active}</strong><small>Can sign in</small></div></article>
        <article className="metric-card inspector-stat-card entrance-up delay-3"><StatIcon type="inactive"/><div><span>Inactive</span><strong>{inactive}</strong><small>Access disabled</small></div></article>
        <article className="metric-card inspector-stat-card entrance-up delay-4"><StatIcon type="id"/><div><span>Inspector IDs</span><strong>{withId}</strong><small>IDs assigned</small></div></article>
      </section>

      <section className="panel inspector-list-panel entrance-up" id="all-inspectors">
        <div className="section-heading-row inspector-list-heading">
          <div>
            <h2>All Inspectors</h2>
            <p className="muted">Select an inspector to manage access.</p>
          </div>
          <div className="inspector-toolbar compact-toolbar">
            <label className="field search-box">
              <span className="sr-only">Search inspectors</span>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search inspector…" />
            </label>
            <label className="field status-box">
              <span className="sr-only">Status</span>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
                <option value="all">All Status</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </label>
          </div>
        </div>

        {inspectors.isLoading ? <p className="muted">Loading inspectors…</p> : null}
        {inspectors.isError ? <div className="notice error">{inspectors.error.message}</div> : null}
        {!inspectors.isLoading && !inspectors.isError && allInspectors.length === 0 ? (
          <div className="empty-state"><h3>No inspectors found</h3><p>Try another search or add a new inspector.</p></div>
        ) : null}

        {allInspectors.length ? (
          <div className="inspector-table-wrap">
            <table className="inspector-table">
              <thead>
                <tr>
                  <th>Inspector ID</th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Phone</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {allInspectors.map((inspector) => (
                  <tr key={inspector.id} className={selectedId === inspector.id ? 'selected' : ''}>
                    <td><code>{inspector.employeeCode || `INSP-${shortId(inspector.id)}`}</code></td>
                    <td><strong>{inspector.name}</strong></td>
                    <td>{inspector.email}</td>
                    <td><span className={`status-dot-label ${inspector.active ? 'active' : 'inactive'}`}>{inspector.active ? 'Active' : 'Inactive'}</span></td>
                    <td>{inspector.phone || <span className="muted">—</span>}</td>
                    <td><button className="kebab-button" type="button" onClick={() => setSelectedId(inspector.id)} aria-label={`Manage ${inspector.name}`}>•••</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <div className="inspector-management-grid">
        <section className="panel form-showcase entrance-up" id="add-inspector">
          <h2>Add New Inspector</h2>
          <p className="muted">Create a new inspector account.</p>
          <form className="stack-form two-column-form" onSubmit={submitCreate}>
            <label className="field"><span>Full Name</span><input required minLength={2} placeholder="e.g. Rohan Verma" value={createForm.fullName} onChange={(event) => setCreateForm({ ...createForm, fullName: event.target.value })} /></label>
            <label className="field"><span>Initial Password</span><input required minLength={8} type="password" autoComplete="new-password" value={createForm.password} onChange={(event) => setCreateForm({ ...createForm, password: event.target.value })} /><small>Minimum 8 characters</small></label>
            <label className="field"><span>Email Address</span><input required type="email" placeholder="e.g. rohan.verma@site.com" autoComplete="off" value={createForm.email} onChange={(event) => setCreateForm({ ...createForm, email: event.target.value })} /></label>
            <label className="field"><span>Confirm Password</span><input required minLength={8} type="password" autoComplete="new-password" value={confirmCreatePassword} onChange={(event) => setConfirmCreatePassword(event.target.value)} /></label>
            <label className="field"><span>Inspector ID</span><input value={createForm.employeeCode ?? ''} onChange={(event) => setCreateForm({ ...createForm, employeeCode: event.target.value })} placeholder="e.g. INSP-1006" /><small>Unique ID for the inspector</small></label>
            <label className="field"><span>Status</span><select value="active" disabled><option>Active</option></select></label>
            <label className="field"><span>Phone Number <small>(Optional)</small></span><input type="tel" placeholder="e.g. +91 98765 43210" value={createForm.phone ?? ''} onChange={(event) => setCreateForm({ ...createForm, phone: event.target.value })} /></label>
            <label className="field"><span>Role</span><select value="inspector" disabled><option>Inspector</option></select></label>
            {confirmCreatePassword && createForm.password !== confirmCreatePassword ? <p className="field-error span-all">Passwords do not match.</p> : null}
            {createMutation.error ? <div className="notice error span-all">{createMutation.error.message}</div> : null}
            <div className="form-actions span-all"><button className="button ghost" type="reset" onClick={() => { setCreateForm(emptyCreate); setConfirmCreatePassword('') }}>Cancel</button><button className="button primary" disabled={createMutation.isPending || createForm.password !== confirmCreatePassword} type="submit">{createMutation.isPending ? 'Creating…' : 'Create Inspector'}</button></div>
          </form>
        </section>

        <section className="panel form-showcase inspector-access-panel entrance-up" id="password-management">
          <h2>Change Inspector Password</h2>
          <p className="muted">Set a new password for an inspector.</p>
          {!selected ? (
            <div className="empty-state compact"><h3>Select an inspector</h3><p>Use the ••• button in the table above.</p></div>
          ) : (
            <>
              <div className="selected-inspector-card">
                <div className="inspector-avatar" aria-hidden="true">{selected.name.slice(0, 1).toUpperCase()}</div>
                <div><strong>{selected.name}</strong><span>{selected.email}</span><code>{selected.employeeCode || `INSP-${shortId(selected.id)}`}</code></div>
              </div>
              <form className="stack-form password-reset-form" onSubmit={submitPassword}>
                <label className="field"><span>New Password</span><input required minLength={8} type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /><small>Minimum 8 characters</small></label>
                <label className="field"><span>Confirm New Password</span><input required minLength={8} type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
                {confirmPassword && password !== confirmPassword ? <p className="field-error">Passwords do not match.</p> : null}
                <div className="account-status-row"><div><strong>Account status</strong><p className="muted">{selected.active ? 'Active and able to sign in.' : 'Inactive and blocked from sign in.'}</p></div><button className={`button ${selected.active ? 'ghost' : 'primary'}`} disabled={accountMutation.isPending} type="button" onClick={() => accountMutation.mutate({ id: selected.id, active: !selected.active })}>{selected.active ? 'Deactivate' : 'Activate'}</button></div>
                <div className="form-actions"><button className="button ghost" type="button" onClick={() => { setPassword(''); setConfirmPassword('') }}>Cancel</button><button className="button primary" disabled={passwordMutation.isPending || password.length < 8 || password !== confirmPassword} type="submit">{passwordMutation.isPending ? 'Updating…' : 'Update Password'}</button></div>
                {passwordMutation.error ? <div className="notice error">{passwordMutation.error.message}</div> : null}
                {accountMutation.error ? <div className="notice error">{accountMutation.error.message}</div> : null}
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
