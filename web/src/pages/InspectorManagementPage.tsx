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

export function InspectorManagementPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [createForm, setCreateForm] = useState<InspectorCreatePayload>(emptyCreate)
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

  return (
    <div className="page-stack inspector-management-page">
      <header className="page-heading inspector-page-heading">
        <div>
          <p className="eyebrow">Team access</p>
          <h1>Inspectors</h1>
          <p>Invite inspectors, see their account ID, and manage access without exposing stored passwords.</p>
        </div>
        <a className="button primary" href="#add-inspector">Add inspector</a>
      </header>

      {successMessage ? <div className="notice success" role="status">{successMessage}</div> : null}

      <section className="inspector-stats" aria-label="Inspector account summary">
        <div className="metric-card"><span>Shown</span><strong>{inspectors.data?.totalItems ?? 0}</strong></div>
        <div className="metric-card"><span>Active</span><strong>{allInspectors.filter((item) => item.active).length}</strong></div>
        <div className="metric-card"><span>Inactive</span><strong>{allInspectors.filter((item) => !item.active).length}</strong></div>
      </section>

      <section className="panel inspector-list-panel">
        <div className="section-heading-row">
          <div>
            <h2>Inspector accounts</h2>
            <p className="muted">Select an inspector to manage their password or account status.</p>
          </div>
        </div>

        <div className="inspector-toolbar">
          <label className="field inspector-search-field">
            <span>Search</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Name, email, or inspector ID"
            />
          </label>
          <label className="field inspector-status-filter">
            <span>Status</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
              <option value="all">All inspectors</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
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
                  <th><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {allInspectors.map((inspector) => (
                  <tr key={inspector.id} className={selectedId === inspector.id ? 'selected' : ''}>
                    <td><code>INSP-{shortId(inspector.id)}</code></td>
                    <td><strong>{inspector.name}</strong>{inspector.employeeCode ? <small>{inspector.employeeCode}</small> : null}</td>
                    <td>{inspector.email}</td>
                    <td><span className={`status-dot-label ${inspector.active ? 'active' : 'inactive'}`}>{inspector.active ? 'Active' : 'Inactive'}</span></td>
                    <td><button className="button ghost compact" type="button" onClick={() => setSelectedId(inspector.id)}>Manage</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      <div className="inspector-management-grid">
        <section className="panel" id="add-inspector">
          <p className="eyebrow">New account</p>
          <h2>Add inspector</h2>
          <p className="muted">Create a login for the Android field app.</p>
          <form className="stack-form" onSubmit={submitCreate}>
            <label className="field"><span>Full name</span><input required minLength={2} value={createForm.fullName} onChange={(event) => setCreateForm({ ...createForm, fullName: event.target.value })} /></label>
            <label className="field"><span>Email</span><input required type="email" autoComplete="off" value={createForm.email} onChange={(event) => setCreateForm({ ...createForm, email: event.target.value })} /></label>
            <label className="field"><span>Inspector / employee ID <small>optional</small></span><input value={createForm.employeeCode ?? ''} onChange={(event) => setCreateForm({ ...createForm, employeeCode: event.target.value })} placeholder="e.g. INSP-1042" /></label>
            <label className="field"><span>Phone <small>optional</small></span><input type="tel" value={createForm.phone ?? ''} onChange={(event) => setCreateForm({ ...createForm, phone: event.target.value })} /></label>
            <label className="field"><span>Initial password</span><input required minLength={8} type="password" autoComplete="new-password" value={createForm.password} onChange={(event) => setCreateForm({ ...createForm, password: event.target.value })} /><small>At least 8 characters.</small></label>
            <button className="button primary" disabled={createMutation.isPending} type="submit">{createMutation.isPending ? 'Creating…' : 'Create inspector'}</button>
            {createMutation.error ? <div className="notice error">{createMutation.error.message}</div> : null}
          </form>
        </section>

        <section className="panel inspector-access-panel">
          <p className="eyebrow">Account access</p>
          <h2>Password & status</h2>
          {!selected ? (
            <div className="empty-state compact"><h3>Select an inspector</h3><p>Use Manage in the table above.</p></div>
          ) : (
            <>
              <div className="selected-inspector-card">
                <div className="inspector-avatar" aria-hidden="true">{selected.name.slice(0, 1).toUpperCase()}</div>
                <div><strong>{selected.name}</strong><span>{selected.email}</span><code>INSP-{shortId(selected.id)}</code></div>
              </div>

              <div className="account-status-row">
                <div><strong>Account status</strong><p className="muted">Inactive inspectors cannot sign in.</p></div>
                <button
                  className={`button ${selected.active ? 'ghost' : 'primary'}`}
                  disabled={accountMutation.isPending}
                  type="button"
                  onClick={() => accountMutation.mutate({ id: selected.id, active: !selected.active })}
                >
                  {selected.active ? 'Deactivate' : 'Activate'}
                </button>
              </div>

              <form className="stack-form password-reset-form" onSubmit={submitPassword}>
                <div><strong>Set a new password</strong><p className="muted">Passwords are never shown or recoverable. Setting a new one replaces the previous password.</p></div>
                <label className="field"><span>New password</span><input required minLength={8} type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
                <label className="field"><span>Confirm password</span><input required minLength={8} type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
                {confirmPassword && password !== confirmPassword ? <p className="field-error">Passwords do not match.</p> : null}
                <button className="button primary" disabled={passwordMutation.isPending || password.length < 8 || password !== confirmPassword} type="submit">{passwordMutation.isPending ? 'Updating…' : 'Update password'}</button>
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
