# SiteProof industrial UI

This redesign uses one runtime visual system for the web and a matching Material 3 system for Android.

Principles:

- adaptive light and dark appearance
- opaque, high-contrast surfaces rather than glassmorphism
- restrained ambient orange blur used only as background depth
- consistent rounded geometry across controls and containers
- minimal information hierarchy with fewer competing panels
- explicit loading, offline, validation, permission, network, retry, and recovery states
- live verification keeps the camera visible while movement guidance overlays the capture

Legacy web theme files remain in the repository for history, but the application entry point imports only `industrial.css` for SiteProof styling.