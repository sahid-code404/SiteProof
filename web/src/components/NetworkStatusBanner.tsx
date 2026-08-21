import { useEffect, useState } from 'react'

export function NetworkStatusBanner() {
  const [online, setOnline] = useState(() => navigator.onLine)

  useEffect(() => {
    const markOnline = () => setOnline(true)
    const markOffline = () => setOnline(false)
    window.addEventListener('online', markOnline)
    window.addEventListener('offline', markOffline)
    return () => {
      window.removeEventListener('online', markOnline)
      window.removeEventListener('offline', markOffline)
    }
  }, [])

  if (online) return null

  return (
    <div className="network-banner" role="status" aria-live="assertive">
      <strong>Network unavailable.</strong>
      <span>SiteProof will keep this page visible, but live verification data cannot refresh until connectivity returns.</span>
    </div>
  )
}
