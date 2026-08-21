import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { Inspector } from '../lib/api'
import {
  createInspector,
  listInspectors,
  resetInspectorPassword,
  updateInspector,
  type InspectorCreatePayload,
} from '../lib/inspectorApi'

type StatusFilter = 'all' | 'active' | 'inactive'
type DialogMode = 'create' | 'edit' | 'password' | null

type EditForm = {
  fullName: string
  employeeCode: string
  phone: string
  active: boolean
}

const emptyCreate: InspectorCreatePayload = {
  fullName: '',
  email: '',
  password: '',
  employeeCode: '',
  phone: '',
}

const emptyEdit: EditForm = {
  fullName: '',
  employeeCode: '',
  phone: '',
  active: true,
}

function shortId(id: string) {
  return id.split('-')[0].toUpperCase()
}

function StatIcon({ type }: { type: 'total' | 'active' | 'inactive' | 'id' }) {
  if (type === 'total') return <span className="stat-icon peach" aria-hidden="true">••</span>
  if (type === 'active') return <span className="stat-icon mint" aria-hidden="true">●</span>
  if (type === 'inactive') return <span className="stat-icon rose" aria-hidden="true">○</span>
  return <span className="stat-icon amber" aria-hidden="true">ID</span>
}

function DialogShell({ title, subtitle, onClose, children, compact = false }: { title: string; subtitle: string; onClose: () => void; children: ReactNode; compact?: boolean }) {
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose() }}>
      <section className={`management-dialog ${compact ? 'compact' : ''}`} role="dialog" aria-modal="true" aria-labelledby="management-dialog-title">
        <header className="dialog-header">
          <div>
            <h2 id="management-dialog-title">{title}</h2>
            <p>{subtitle}</p>
          </div>
          <button className="dialog-close" type="button" onClick={onClose} aria-label="Close dialog">×</button>
        </header>
        <div className="dialog-body">{children}</div>
      </section>
    </div>
  )
}

function InspectorIdentity({ inspector }: { inspector: Inspector }) {
  return (
    <div className="dialog-inspector-identity">
      <span className="inspector-avatar" aria-hidden="true">{inspector.name.slice(0, 1).toUpperCase()}</span>
      <div>
        <strong>{inspector.name}</strong>
        <span>{inspector.email}</span>
        <small>{inspector.employeeCode || `INSP-${shortId(inspector.id)}`}</small>
      </div>
    </div>
  )
}

export function InspectorManagementPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [menuId, setMenuId] = useState<string | null>(null)
  const [dialog, setDialog] = useState<DialogMode>(null)
  const [selectedInspector, setSelectedInspector] = useState<Inspector | null>(null)
  const [createForm, setCreateForm] = useState<InspectorCreatePayload>(emptyCreate)
  const [confirmCreatePassword, setConfirmCreatePassword] = useState('')
  const [editForm, setEditForm] = useState<EditForm>(emptyEdit)
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const activeFilter = statusFilter === 'all' ? undefined : statusFilter === 'active'
  const inspectors = useQuery({
    queryKey: ['inspector-management', search, activeFilter],
    queryFn: () => listInspectors(search, activeFilter),
  })
  const summaryInspectors = useQuery({
    queryKey: ['inspector-management-summary'],
    queryFn: () => listInspectors('', undefined),
    staleTime: 30_000,
  })

  const allInspectors = useMemo(() => inspectors.data?.items ?? [], [inspectors.data?.items])
  const summaryItems = summaryInspectors.data?.items ?? []

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        if (dialog) setDialog(null)
        else setMenuId(null)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [dialog])

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ['inspector-management'] })
    queryClient.invalidateQueries({ queryKey: ['inspector-management-summary'] })
    queryClient.invalidateQueries({ queryKey: ['inspectors'] })
  }

  function closeDialog() {
    setDialog(null)
    setPassword('')
    setConfirmPassword('')
  }

  function openCreate() {
    setSuccessMessage(null)
    setCreateForm(emptyCreate)
    setConfirmCreatePassword('')
    setSelectedInspector(null)
    setMenuId(null)
    setDialog('create')
  }

  function openEdit(inspector: Inspector) {
    setSelectedInspector(inspector)
    setEditForm({
      fullName: inspector.name,
      employeeCode: inspector.employeeCode ?? '',
      phone: inspector.phone ?? '',
      active: inspector.active,
    })
    setMenuId(null)
    setDialog('edit')
  }

  function openPassword(inspector: Inspector) {
    setSelectedInspector(inspector)
    setPassword('')
    setConfirmPassword('')
    setMenuId(null)
    setDialog('password')
  }

  const createMutation = useMutation({
    mutationFn: createInspector,
    onSuccess: (created) => {
      setCreateForm(emptyCreate)
      setConfirmCreatePassword('')
      setSuccessMessage(`${created.name} can now sign in to the Android app.`)
      setDialog(null)
      refresh()
    },
  })

  const editMutation = useMutation({
    mutationFn: ({ id, form }: { id: string; form: EditForm }) => updateInspector(id, {
      fullName: form.fullName.trim(),
      employeeCode: form.employeeCode.trim() || null,
      phone: form.phone.trim() || null,
      active: form.active,
    }),
    onSuccess: (updated) => {
      setSelectedInspector(updated)
      setSuccessMessage(`${updated.name}'s account was updated.`)
      setDialog(null)
      refresh()
    },
  })

  const passwordMutation = useMutation({
    mutationFn: ({ id, nextPassword }: { id: string; nextPassword: string }) => resetInspectorPassword(id, nextPassword),
    onSuccess: () => {
      setPassword('')
      setConfirmPassword('')
      setSuccessMessage('Password updated. The previous password no longer works.')
      setDialog(null)
    },
  })

  function submitCreate(event: FormEvent) {
    event.preventDefault()
    if (createForm.password.length < 8 || createForm.password !== confirmCreatePassword) return
    setSuccessMessage(null)
    createMutation.mutate({
      ...createForm,
      fullName: createForm.fullName.trim(),
      email: createForm.email.trim().toLowerCase(),
      employeeCode: createForm.employeeCode?.trim() || undefined,
      phone: createForm.phone?.trim() || undefined,
    })
  }

  function submitEdit(event: FormEvent) {
    event.preventDefault()
    if (!selectedInspector || editForm.fullName.trim().length < 2) return
    setSuccessMessage(null)
    editMutation.mutate({ id: selectedInspector.id, form: editForm })
  }

  function submitPassword(event: FormEvent) {
    event.preventDefault()
    if (!selectedInspector || password.length < 8 || password !== confirmPassword) return
    setSuccessMessage(null)
    passwordMutation.mutate({ id: selectedInspector.id, nextPassword: password })
  }

  const total = summaryInspectors.data?.totalItems ?? inspectors.data?.totalItems ?? 0
  const active = summaryItems.filter((item) => item.active).length
  const inactive = summaryItems.filter((item) => !item.active).length
  const withId = summaryItems.filter((item) => item.employeeCode).length

  return (
    <div className="page-stack inspector-management-page">
      <header className="page-heading inspector-page-heading entrance-up">
        <div>
          <p className="eyebrow">Access management</p>
          <h1>Inspectors</h1>
          <p>Manage field accounts without leaving this page.</p>
        </div>
        <button className="button primary add-inspector-button" type="button" onClick={openCreate}><span aria-hidden="true">＋</span> Add inspector</button>
      </header>

      {successMessage ? <div className="notice success entrance-up compact-success" role="status">{successMessage}</div> : null}

      <section className="inspector-stats" aria-label="Inspector account summary">
        <article className="metric-card inspector-stat-card entrance-up delay-1"><StatIcon type="total"/><div><span>Total inspectors</span><strong>{total}</strong><small>All accounts</small></div></article>
        <article className="metric-card inspector-stat-card entrance-up delay-2"><StatIcon type="active"/><div><span>Active</span><strong>{active}</strong><small>Can sign in</small></div></article>
        <article className="metric-card inspector-stat-card entrance-up delay-3"><StatIcon type="inactive"/><div><span>Inactive</span><strong>{inactive}</strong><small>Access disabled</small></div></article>
        <article className="metric-card inspector-stat-card entrance-up delay-4"><StatIcon type="id"/><div><span>Inspector IDs</span><strong>{withId}</strong><small>IDs assigned</small></div></article>
      </section>

      <section className="panel inspector-list-panel entrance-up" id="all-inspectors">
        <div className="section-heading-row inspector-list-heading">
          <div>
            <h2>All inspectors</h2>
            <p className="muted">Search accounts or use the action menu to edit access and passwords.</p>
          </div>
          <div className="inspector-toolbar compact-toolbar">
            <label className="field search-box">
              <span className="sr-only">Search inspectors</span>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search inspector…" />
            </label>
            <label className="field status-box">
              <span className="sr-only">Status</span>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
                <option value="all">All status</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </label>
          </div>
        </div>

        {inspectors.isLoading ? <div className="table-loading-state" role="status">Loading inspectors…</div> : null}
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
                  <th><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {allInspectors.map((inspector) => (
                  <tr key={inspector.id}>
                    <td><code>{inspector.employeeCode || `INSP-${shortId(inspector.id)}`}</code></td>
                    <td><strong>{inspector.name}</strong></td>
                    <td>{inspector.email}</td>
                    <td><span className={`status-dot-label ${inspector.active ? 'active' : 'inactive'}`}>{inspector.active ? 'Active' : 'Inactive'}</span></td>
                    <td>{inspector.phone || <span className="muted">—</span>}</td>
                    <td className="action-cell">
                      <div className="row-menu-anchor">
                        <button className="kebab-button" type="button" onClick={() => setMenuId(menuId === inspector.id ? null : inspector.id)} aria-label={`Actions for ${inspector.name}`} aria-expanded={menuId === inspector.id}>•••</button>
                        {menuId === inspector.id ? (
                          <div className="row-action-menu" role="menu" aria-label={`Actions for ${inspector.name}`}>
                            <button type="button" role="menuitem" onClick={() => openEdit(inspector)}><strong>Edit account</strong><span>Name, ID, phone and status</span></button>
                            <button type="button" role="menuitem" onClick={() => openPassword(inspector)}><strong>Change password</strong><span>Set a new sign-in password</span></button>
                          </div>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      {dialog === 'create' ? (
        <DialogShell title="Add inspector" subtitle="Create a field account. The inspector can sign in immediately after creation." onClose={closeDialog}>
          <form className="modal-form-grid" onSubmit={submitCreate}>
            <label className="field"><span>Full name</span><input autoFocus required minLength={2} placeholder="e.g. Rohan Verma" value={createForm.fullName} onChange={(event) => setCreateForm({ ...createForm, fullName: event.target.value })} /></label>
            <label className="field"><span>Email address</span><input required type="email" placeholder="rohan.verma@site.com" autoComplete="off" value={createForm.email} onChange={(event) => setCreateForm({ ...createForm, email: event.target.value })} /></label>
            <label className="field"><span>Inspector ID</span><input value={createForm.employeeCode ?? ''} onChange={(event) => setCreateForm({ ...createForm, employeeCode: event.target.value })} placeholder="e.g. INSP-1006" /><small>Optional unique field ID</small></label>
            <label className="field"><span>Phone number</span><input type="tel" placeholder="e.g. +91 98765 43210" value={createForm.phone ?? ''} onChange={(event) => setCreateForm({ ...createForm, phone: event.target.value })} /><small>Optional</small></label>
            <label className="field"><span>Initial password</span><input required minLength={8} type="password" autoComplete="new-password" value={createForm.password} onChange={(event) => setCreateForm({ ...createForm, password: event.target.value })} /><small>Minimum 8 characters</small></label>
            <label className="field"><span>Confirm password</span><input required minLength={8} type="password" autoComplete="new-password" value={confirmCreatePassword} onChange={(event) => setConfirmCreatePassword(event.target.value)} /></label>
            {confirmCreatePassword && createForm.password !== confirmCreatePassword ? <p className="field-error span-all">Passwords do not match.</p> : null}
            {createMutation.error ? <div className="notice error span-all">{createMutation.error.message}</div> : null}
            <div className="dialog-actions span-all"><button className="button ghost" type="button" onClick={closeDialog}>Cancel</button><button className="button primary" disabled={createMutation.isPending || createForm.password !== confirmCreatePassword} type="submit">{createMutation.isPending ? 'Creating…' : 'Create inspector'}</button></div>
          </form>
        </DialogShell>
      ) : null}

      {dialog === 'edit' && selectedInspector ? (
        <DialogShell title="Edit inspector" subtitle="Update the field account without changing its email or history." onClose={closeDialog}>
          <InspectorIdentity inspector={selectedInspector} />
          <form className="modal-form-grid" onSubmit={submitEdit}>
            <label className="field"><span>Full name</span><input autoFocus required minLength={2} value={editForm.fullName} onChange={(event) => setEditForm({ ...editForm, fullName: event.target.value })} /></label>
            <label className="field"><span>Inspector ID</span><input value={editForm.employeeCode} onChange={(event) => setEditForm({ ...editForm, employeeCode: event.target.value })} /></label>
            <label className="field"><span>Phone number</span><input type="tel" value={editForm.phone} onChange={(event) => setEditForm({ ...editForm, phone: event.target.value })} placeholder="Optional" /></label>
            <label className="field"><span>Account status</span><select value={editForm.active ? 'active' : 'inactive'} onChange={(event) => setEditForm({ ...editForm, active: event.target.value === 'active' })}><option value="active">Active · can sign in</option><option value="inactive">Inactive · access disabled</option></select></label>
            {editMutation.error ? <div className="notice error span-all">{editMutation.error.message}</div> : null}
            <div className="dialog-actions span-all"><button className="button ghost" type="button" onClick={closeDialog}>Cancel</button><button className="button primary" disabled={editMutation.isPending || editForm.fullName.trim().length < 2} type="submit">{editMutation.isPending ? 'Saving…' : 'Save changes'}</button></div>
          </form>
        </DialogShell>
      ) : null}

      {dialog === 'password' && selectedInspector ? (
        <DialogShell compact title="Change password" subtitle="The previous password stops working as soon as this change is saved." onClose={closeDialog}>
          <InspectorIdentity inspector={selectedInspector} />
          <form className="password-dialog-form" onSubmit={submitPassword}>
            <label className="field"><span>New password</span><input autoFocus required minLength={8} type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} /><small>Minimum 8 characters</small></label>
            <label className="field"><span>Confirm new password</span><input required minLength={8} type="password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
            {confirmPassword && password !== confirmPassword ? <p className="field-error">Passwords do not match.</p> : null}
            {passwordMutation.error ? <div className="notice error">{passwordMutation.error.message}</div> : null}
            <div className="dialog-actions"><button className="button ghost" type="button" onClick={closeDialog}>Cancel</button><button className="button primary" disabled={passwordMutation.isPending || password.length < 8 || password !== confirmPassword} type="submit">{passwordMutation.isPending ? 'Updating…' : 'Update password'}</button></div>
          </form>
        </DialogShell>
      ) : null}
    </div>
  )
}
