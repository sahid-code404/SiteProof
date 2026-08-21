import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { SplashScreen } from './components/SplashScreen'
import { getToken, getStoredUser } from './lib/auth'
import { DashboardPage } from './pages/DashboardPage'
import { InspectionDetailPage } from './pages/InspectionDetailPage'
import { InspectionFormPage } from './pages/InspectionFormPage'
import { InspectorManagementPage } from './pages/InspectorManagementPage'
import { InspectionsPage } from './pages/InspectionsPage'
import { LoginPage } from './pages/LoginPage'
import { PublicReceiptPage } from './pages/PublicReceiptPage'
import { ReceiptDetailPage } from './pages/ReceiptDetailPage'
import { ReviewWorkspacePage } from './pages/ReviewWorkspacePage'

function ProtectedApp() {
  if (!getToken()) return <Navigate to="/login" replace />
  const user = getStoredUser()
  if (user?.role === 'INSPECTOR') {
    return <div className="center-card"><h1>Admin dashboard unavailable</h1><p>Inspectors use the Android application for assignments.</p></div>
  }
  const canManage = user?.role === 'ADMIN'
  const canReview = user?.role === 'ADMIN' || user?.role === 'REVIEWER'
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/review" element={canReview ? <ReviewWorkspacePage /> : <Navigate to="/" replace />} />
        <Route path="/inspections" element={<InspectionsPage />} />
        <Route path="/inspectors" element={canManage ? <InspectorManagementPage /> : <Navigate to="/" replace />} />
        <Route path="/inspections/new" element={canManage ? <InspectionFormPage /> : <Navigate to="/inspections" replace />} />
        <Route path="/inspections/:id/edit" element={canManage ? <InspectionFormPage /> : <Navigate to="/inspections" replace />} />
        <Route path="/inspections/:id" element={<InspectionDetailPage />} />
        <Route path="/receipts/:id" element={<ReceiptDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  const [splashVisible, setSplashVisible] = useState(true)

  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const timer = window.setTimeout(() => setSplashVisible(false), reducedMotion ? 120 : 900)
    return () => window.clearTimeout(timer)
  }, [])

  if (splashVisible) return <SplashScreen />

  return (
    <Routes>
      <Route path="/verify/:token" element={<PublicReceiptPage />} />
      <Route path="/login" element={getToken() ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/*" element={<ProtectedApp />} />
    </Routes>
  )
}
