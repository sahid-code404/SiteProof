import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { getToken, getStoredUser } from './lib/auth'
import { DashboardPage } from './pages/DashboardPage'
import { InspectionDetailPage } from './pages/InspectionDetailPage'
import { InspectionFormPage } from './pages/InspectionFormPage'
import { InspectionsPage } from './pages/InspectionsPage'
import { LoginPage } from './pages/LoginPage'

function ProtectedApp() {
  if (!getToken()) return <Navigate to="/login" replace />
  const user = getStoredUser()
  if (user?.role === 'INSPECTOR') {
    return <div className="center-card"><h1>Admin dashboard unavailable</h1><p>Inspectors use the Android application for assignments.</p></div>
  }
  const canManage = user?.role === 'ADMIN'
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/inspections" element={<InspectionsPage />} />
        <Route path="/inspections/new" element={canManage ? <InspectionFormPage /> : <Navigate to="/inspections" replace />} />
        <Route path="/inspections/:id/edit" element={canManage ? <InspectionFormPage /> : <Navigate to="/inspections" replace />} />
        <Route path="/inspections/:id" element={<InspectionDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={getToken() ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/*" element={<ProtectedApp />} />
    </Routes>
  )
}
