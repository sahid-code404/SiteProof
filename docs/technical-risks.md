# Major Technical Risks

1. **Android sensor variance** — sampling rates, sensor availability, calibration, and coordinate conventions vary by device. Create a normalized sensor abstraction before challenge scoring.
2. **Camera/sensor synchronization** — timestamps must use monotonic clocks where possible; wall-clock time alone is not enough.
3. **Replay detection overclaiming** — screen/replay detection is heuristic. Treat it as a risk signal, not proof.
4. **GPS spoofing** — location can be manipulated. Combine location confidence with challenge, device integrity, motion, and environmental signals.
5. **Play Integrity development limits** — production attestation can be awkward on emulators/debug builds. Keep an interface with a development provider.
6. **Evidence upload size** — short videos plus sensor batches must be compressed and uploaded reliably, especially on poor field networks.
7. **CV processing cost** — downsample frames/keyframes and avoid full-resolution work unless required.
8. **Scoring calibration** — deterministic weights must remain configuration-driven and explainable.
9. **Scope creep** — optional AI, Wi-Fi fingerprinting, advanced replay detection and offline challenge batches must wait until the MVP flow works.
