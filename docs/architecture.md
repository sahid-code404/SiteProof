# SiteProof Architecture — through Phase 2

## Boundaries

SiteProof remains a monorepo with three user-facing/runtime components and shared infrastructure:

```text
Admin browser                    Inspector Android
     │                                  │
     └──────── HTTPS/REST ──────────────┘
                    │
                FastAPI API
                    │
       service/domain transaction layer
                    │
            SQLAlchemy repositories
                    │
                PostgreSQL
```

MinIO remains available in local infrastructure for later evidence phases but Phase 2 does not upload evidence.

## Backend

FastAPI route handlers are deliberately thin. Authentication/authorization is resolved through dependencies, then domain operations are delegated to services:

- `InspectionService` functions own lifecycle rules, organization scoping, pagination and dashboard counts.
- assignment operations execute in one database transaction and lock the inspection row before changing assignment state;
- `InspectorService` owns organization-scoped inspector lookup/listing/creation;
- `AuditService` writes server-side audit records in the same transaction as the business event;
- Pydantic API schemas are separate from SQLAlchemy persistence models;
- Alembic owns database schema evolution. Runtime `create_all()` bootstrapping was removed.

The database-level partial unique index on `inspection_assignments.inspection_id` where status is `ACTIVE` prevents more than one active assignment per inspection.

## Multi-organization isolation

`users`, `inspectors`, `inspections`, `inspection_assignments` and `audit_logs` all carry `organization_id` where required. Backend queries always scope records by the authenticated user's organization. Inspectors receive an additional active-assignment predicate, so knowing another inspection UUID is not sufficient to read it.

## Authentication

Passwords use Argon2. Access tokens are JWTs signed by the backend and include the user ID, role and organization ID. The backend reloads the user from the database on authenticated requests rather than trusting role/organization claims alone.

The Android app stores its access token encrypted with an Android Keystore AES-GCM key. The browser stores the session token in local storage for the Phase 2 prototype; production hardening should move browser auth toward a protected HttpOnly cookie/refresh-token design.

## Web dashboard

React + TypeScript + TanStack Query + React Router implement:

- authenticated admin/reviewer shell;
- real dashboard summary;
- inspection list with search, status, priority, inspector filters and pagination;
- create/edit forms;
- Leaflet/OpenStreetMap coordinate picker and site preview;
- assignment/reassignment/cancellation controls for admins;
- read-only compatibility for reviewer accounts.

All mutations invalidate affected TanStack Query caches rather than requiring a full-page reload.

## Android

The inspector app follows:

```text
Compose UI → ViewModel/StateFlow → InspectionRepository → Retrofit API
                                      │
                                      └→ local assignment cache
```

The local cache is a small private SharedPreferences/Moshi store because Room did not exist in Phase 1. Phase 2 only needs cached assignment metadata; introducing a second persistence architecture solely for this milestone would add unnecessary complexity. The cache is cleared on sign-out/login so one inspector cannot inherit another inspector's offline list.

The UI provides loading, empty, error and offline states plus pull-to-refresh. Offline data is read-only. Status-changing operations require network connectivity.

## Explicit Phase 2 boundary

There is no CameraX capture, sensor acquisition, challenge generation, evidence upload, OpenCV, device attestation, Wi-Fi fingerprinting or trust scoring in this architecture yet.
