# SiteProof

**Active Multi-Sensor Proof-of-Physical-Presence and Tamper-Resistant Field Verification System**

SiteProof is a full-stack infrastructure field-inspection platform with a native Android inspector app, FastAPI/PostgreSQL backend, and React reviewer dashboard.

## Current Phase 7 capability

```text
Android live capture
  → location + synchronized sensors + continuous video
  → server-randomized movement challenges
  → Phase 4 physical sensor validation
  → Phase 5 independent camera-motion / continuity analysis
  → Phase 6 camera ↔ physical-motion consistency
  → Phase 7 seven-signal policy engine
  → SiteProof score (0–100)
  → VERIFIED / REVIEW REQUIRED / FLAGGED / INCONCLUSIVE
  → deterministic explanation
  → separate human review decision
```

The score means **confidence derived from multiple independent verification signals under the configured SiteProof verification policy**. It does not mean “100% authentic”, legal proof, or impossible to fake.

## Default Phase 7 policy

```text
Location                         15
Session / Time                    5
Random Challenges               20
Sensor Evidence                 15
Visual Evidence                 10
Scene Continuity                10
Visual–Inertial Consistency     25
                                ──
Total                           100
```

Default thresholds are `VERIFIED >= 85`, `REVIEW_REQUIRED >= 65`, otherwise `FLAGGED`. Required technically insufficient evidence yields `INCONCLUSIVE`. Overall confidence is separate from the score and must meet the policy minimum for automatic verification. High-confidence fusion mismatch, wrong location, repeated challenge failures and major scene discontinuity are explicit hard rules.

See `docs/verification-engine.md` for the exact v1.0 calculation and limitations.

## Repository structure

```text
siteproof/
├── android/
├── backend/
├── web/
├── docs/
├── infrastructure/
├── scripts/
├── .github/workflows/
├── docker-compose.yml
└── .env.example
```

## Quick start

```bash
cp .env.example .env
# Change JWT_SECRET and local passwords.
docker compose up --build
```

Open reviewer UI at `http://localhost:5173`, OpenAPI at `http://localhost:8000/docs`, and health at `http://localhost:8000/health`.

## Backend checks

```bash
cd backend
pip install -e '.[dev]'
alembic upgrade head
pytest -q
ruff check app tests alembic
```

Phase 7 migration head is `0007_phase7_verification_engine`.

## Web checks

```bash
cd web
npm install
npm test
npm run lint
npm run build
```

The inspection detail page shows the Phase 7 SiteProof report first, followed by existing Phase 4–6 evidence drill-down. Authorized reviewers see score, confidence, policy/engine version, per-signal contribution, hard-rule overrides, explanations and human review controls.

## Android checks

```bash
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

The inspector app deliberately receives a simplified Phase 7 operational message and does not expose reviewer score breakdown or hard-rule/anti-spoofing diagnostics.

## Phase 7 APIs

```text
GET  /api/v1/sessions/{sessionId}/verification
POST /api/v1/sessions/{sessionId}/verification/recalculate   # ADMIN
POST /api/v1/inspections/{inspectionId}/review               # ADMIN/REVIEWER
```

Human review decisions (`APPROVED`, `REJECTED`, `RECAPTURE_REQUIRED`) are stored separately from the automated verification verdict.

## Real-device acceptance remains mandatory

Automated CI can validate migrations, deterministic scoring, API authorization, web behavior and Android compilation. It cannot prove that real phone location/sensor/camera evidence produces calibrated Phase 7 scores.

Before Phase 7 can be called accepted, record actual results for a legitimate full SiteProof session, controlled basic mismatch/replay scenario, wrong-location/geofence behavior, and poor-evidence scenario. Do not manipulate thresholds to force a demo result and do not fabricate measurements.

## Phase boundary

Phase 7 does **not** implement cryptographic signed receipts, server signing keys, C2PA, Play Integrity scoring, Wi-Fi scoring, advanced replay classification or ML anomaly scoring. Those belong to **Phase 8 — Evidence Integrity, Cryptographic Manifest & Signed Verification Receipts** and later phases. Phase 8 must not start until real Phase 7 acceptance is recorded.
