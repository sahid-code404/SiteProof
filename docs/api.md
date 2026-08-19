# SiteProof REST API — through Phase 7

Base path: `/api/v1`

Authenticated endpoints use `Authorization: Bearer <access-token>`. FastAPI OpenAPI at `/docs` is the executable schema source. Organization scope and role checks remain enforced by the backend; cross-organization resources may intentionally return 404.

## Existing inspection and capture APIs

Phase 1–6 routes remain in place:

```text
POST /auth/login
GET  /auth/me
GET  /inspectors
POST /inspectors
GET  /inspections
GET  /inspections/summary
POST /inspections
GET  /inspections/{inspectionId}
PATCH /inspections/{inspectionId}
POST /inspections/{inspectionId}/assign
POST /inspections/{inspectionId}/reassign
POST /inspections/{inspectionId}/acknowledge
POST /inspections/{inspectionId}/ready
POST /inspections/{inspectionId}/cancel
POST /inspections/{inspectionId}/sessions
GET  /inspections/{inspectionId}/sessions/latest
GET  /sessions/{sessionId}
POST /sessions/{sessionId}/start-capture
POST /sessions/{sessionId}/capture-complete
POST /sessions/{sessionId}/abort
POST /sessions/{sessionId}/challenges/next
POST /challenges/{challengeId}/start
POST /challenges/{challengeId}/submit
GET  /sessions/{sessionId}/challenges
POST /sessions/{sessionId}/evidence/initiate
PUT  /sessions/{sessionId}/evidence/{fileId}/content
POST /sessions/{sessionId}/evidence/complete
GET  /sessions/{sessionId}/evidence
GET  /sessions/{sessionId}/evidence/{fileId}/content
GET  /sessions/{sessionId}/visual-analysis
POST /sessions/{sessionId}/visual-analysis/retry
GET  /sessions/{sessionId}/fusion-analysis
POST /sessions/{sessionId}/fusion-analysis/retry
```

Phase 4 challenge results are server-derived. Phase 5 is independent camera evidence. Phase 6 is cross-signal evidence, not itself the final SiteProof verdict.

## Phase 7 verification result

### `GET /sessions/{sessionId}/verification`

Roles: authenticated `ADMIN`, `REVIEWER`, or owning `INSPECTOR`.

Detailed admin/reviewer response includes processing status, score, raw score, confidence, verdict, policy id/name/version, `verification-engine-v1.0`, calculation revision, seven signal breakdown rows, hard-rule codes, summary reasons/warnings, latest human review and calculated timestamp.

Numeric examples in documentation illustrate schema only and are not claimed project measurements.

Inspector response uses the same resource but `detailed=false`; score, confidence, signal breakdown and hard-rule diagnostics are withheld. The inspector receives a simplified operational summary such as “Evidence accepted by automated checks” or “Verification is under review.”

Processing states:

```text
PENDING
WAITING_FOR_SIGNALS
CALCULATING
COMPLETED
FAILED
```

Verdicts:

```text
VERIFIED
REVIEW_REQUIRED
FLAGGED
INCONCLUSIVE
```

No response field means legal certainty or “100% genuine”.

## Recalculation

### `POST /sessions/{sessionId}/verification/recalculate`

Role: `ADMIN` only.

Optional body:

```json
{"policyVersion": "1.0"}
```

Recalculation is queued and creates a new calculation revision. Historical results are preserved.

## Human review

### `POST /inspections/{inspectionId}/review`

Roles: `ADMIN` or `REVIEWER`.

```json
{
  "sessionId": "uuid",
  "decision": "APPROVED",
  "reason": "Evidence and inspection context are acceptable."
}
```

Decision values are `APPROVED`, `REJECTED`, and `RECAPTURE_REQUIRED`. A completed automated result is required. Human review remains separate from the automated verdict.

## Phase 7 audit events

```text
VERIFICATION_STARTED
VERIFICATION_COMPLETED
VERIFICATION_RECALCULATED
VERIFICATION_FLAGGED
VERIFICATION_INCONCLUSIVE
REVIEW_APPROVED
REVIEW_REJECTED
RECAPTURE_REQUESTED
```

Audit metadata contains compact engine/policy/score/verdict information, not giant evidence diagnostics.

## Security boundary

No LLM decides pass/fail. Scoring, confidence gates, hard rules, verdicts and explanations are deterministic. Phase 7 does not implement Phase 8 signing keys, signed receipts, C2PA, Play Integrity/Wi-Fi scoring, advanced replay classification or ML anomaly scoring.
