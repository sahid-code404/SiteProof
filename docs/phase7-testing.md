# Phase 7 Testing & Calibration

This document records the Phase 7-specific test plan. Existing Phase 3–6 hardware/video acceptance requirements remain prerequisites and are not replaced by synthetic trust-engine tests.

## Automated backend

```bash
cd backend
alembic upgrade head
alembic downgrade 0006_phase6_visual_inertial
alembic upgrade head
ruff check app tests alembic
pytest -q
```

Phase 7 coverage includes policy validation, exact score boundaries, score/confidence separation, mandatory evidence handling, fusion/location/challenge hard rules, poor GPS, required visual failure, idempotency, recalculation history, policy version history, authorization, inspector masking, cross-organization isolation and separate human review.

## Web

```bash
cd web
npm install
npm test
npm run lint
npm run build
```

Reviewer acceptance must confirm precise verdict banners, hard-rule override visibility, signal breakdown, approve/reject/recapture actions, and preservation of Phase 4–6 evidence drill-down.

## Android

```bash
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

The inspector app must compile with the simplified Phase 7 status fetch and must not expose score breakdown, security thresholds or hard-rule diagnostics.

## Required real Phase 7 acceptance

Do not replace `NOT TESTED YET` with invented values.

### Session A — legitimate

```text
Device model:                 NOT TESTED YET
Android version:              NOT TESTED YET
App/commit:                   NOT TESTED YET
Phase 4 challenge outcome:    NOT TESTED YET
Phase 5 visual outcome:       NOT TESTED YET
Phase 6 fusion outcome:       NOT TESTED YET
Phase 7 score:                NOT TESTED YET
Phase 7 confidence:           NOT TESTED YET
Phase 7 verdict:              NOT TESTED YET
Trust-engine processing time: NOT TESTED YET
```

A legitimate session does not have to be forced into VERIFIED. If it receives REVIEW_REQUIRED or INCONCLUSIVE, inspect and record the actual weak signal.

### Session B — controlled basic replay / mismatch

```text
Observed sensor movement:     NOT TESTED YET
Observed visual movement:     NOT TESTED YET
Phase 6 mismatch/confidence:  NOT TESTED YET
Phase 7 raw score:            NOT TESTED YET
Hard rule codes:              NOT TESTED YET
Phase 7 verdict:              NOT TESTED YET
```

Expected architecture is high-confidence fusion mismatch → hard rule → not VERIFIED. Actual evidence remains the source of truth.

### Session C — poor evidence

```text
Visual quality:               NOT TESTED YET
Continuity:                   NOT TESTED YET
Fusion:                       NOT TESTED YET
Phase 7 score:                NOT TESTED YET
Phase 7 verdict:              NOT TESTED YET
```

Expected behavior is INCONCLUSIVE or REVIEW_REQUIRED where evidence is technically insufficient, not an automatic accusation.

### Wrong-location behavior

The current live-capture backend may reject a clearly out-of-radius session before a complete evidence package exists. Record the **actual** observed geofence behavior. The Phase 7 location hard rule is a defensive rule for a persisted high-confidence outside-radius signal; do not bypass upstream controls merely to manufacture a score.

## Calibration

Collect real legitimate, low-quality and controlled mismatch samples before tuning policy values. Evaluate score/confidence distributions, location uncertainty, challenge failure/inconclusive rates, visual/continuity/fusion distributions, hard-rule activation and trust calculation runtime.

Do not train an ML model in Phase 7 and do not tune thresholds solely to make the demo pass.
