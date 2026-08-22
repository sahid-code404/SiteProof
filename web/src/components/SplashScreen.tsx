export function SplashScreen() {
  return (
    <div className="sp-splash" role="status" aria-label="Opening SiteProof">
      <div className="sp-splash-core">
        <div className="sp-splash-mark" aria-hidden="true">
          <img src="/siteproof-icon.svg" alt="" />
        </div>
        <strong>SiteProof</strong>
        <span>Trusted field verification</span>
      </div>
    </div>
  )
}
