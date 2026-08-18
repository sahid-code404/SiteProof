# SiteProof Architecture — Phase 1

## Component boundaries

### Android capture application
Owns inspector-facing workflow, device permissions, future live CameraX capture, sensors, location, local secure session storage, and reliable upload orchestration. It must never calculate the authoritative verification verdict.

### Backend API
Owns authentication, authorization, inspection state transitions, challenge issuance, evidence metadata, verification orchestration, audit records, and the final trust decision.

### Web dashboard
Owns administrator/reviewer workflows and presentation only. Business-critical authorization and transitions remain server-side.

### PostgreSQL
System of record for relational business and verification metadata.

### MinIO / S3-compatible storage
Stores future evidence objects. Database rows reference objects and integrity metadata; raw evidence is not placed in relational columns.

## Phase 1 database entities

Implemented now:
- `users`
- `organizations`

Reserved for Phase 2+:
- inspectors
- inspections
- inspection_assignments
- verification_sessions
- challenges
- challenge_results
- sensor_packages
- location_samples
- evidence_files
- verification_results
- verification_signals
- device_attestations
- audit_logs
- review_decisions
- signed_receipts

## API boundary

Implemented:
- `GET /health`
- `POST /api/v1/auth/login`

Phase 2 starts inspection CRUD and assignment APIs.

## Android architecture direction

Use feature-oriented packages with explicit interfaces around camera, location, sensor capture, attestation, secure storage, networking, and upload scheduling. Compose UI observes state from ViewModels; device APIs stay behind repositories/services so challenge verification logic can be tested independently.

## Web architecture direction

Use React + TypeScript. TanStack Query owns server-state caching. UI pages never become a source of truth for permissions, trust score, or inspection transitions.

## Local Docker architecture

Browser -> web container -> backend API -> PostgreSQL
                                      -> MinIO (Phase 3 evidence)
Android/emulator -> backend API

## Security baseline

- Secrets only through environment configuration.
- JWT access tokens are created server-side.
- Passwords use Argon2 hashing.
- CORS origins are configured explicitly.
- The client never sends a trusted role or verification score.
