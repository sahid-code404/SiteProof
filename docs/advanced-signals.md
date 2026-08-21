# Phase 10 — Environment Continuity and Statistical Anomaly Intelligence

Phase 10 adds two optional, explainable signals on top of the accepted Phase 9 anti-spoofing layer.

## Privacy-preserving Wi-Fi continuity

The Android app samples the visible Wi-Fi environment at the start and end of a live verification session.

Privacy rules:

- SSIDs are never stored.
- Raw BSSIDs are never stored.
- Each BSSID is SHA-256 hashed with a domain separator and the current verification session ID.
- The same access point can be compared within one session, but the stored identifier cannot be linked across sessions.
- At most 12 strongest access points are retained per snapshot.
- Wi-Fi is supporting evidence only. Missing Wi-Fi observations never fail verification.

The backend compares start/end access-point overlap with a Jaccard score and compares RSSI stability for overlapping access points. The output is `CONSISTENT`, `PARTIAL`, `MISMATCH`, `LIMITED`, or `UNAVAILABLE` with a separate confidence value.

## Deterministic statistical anomaly score

The anomaly layer deliberately does not use a black-box trained model. It combines normalized, auditable features from existing verification evidence:

- sensor anomaly score;
- terminal Phase 6 fusion disagreement;
- camera/sensor timing residual;
- approximate angle residual;
- duplicate-frame ratio;
- location risk;
- environment discontinuity when sufficiently confident.

Same-direction camera/sensor angle differences are capped because Phase 5 camera angle is an approximate projective measurement and can be distorted by ordinary hand shake or feature-window truncation.

The output is `NOMINAL`, `ELEVATED`, or `HIGH` plus a 0–1 anomaly score and per-feature diagnostics.

## Security boundary

Phase 10 is corroborating evidence. It does not replace the Phase 7 verification engine, Phase 8 cryptographic receipt, or Phase 9 deterministic anti-spoofing checks. A Wi-Fi mismatch by itself never creates a final verification failure.
