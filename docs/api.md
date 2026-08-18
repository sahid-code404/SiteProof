# SiteProof REST API — Phase 2

Base path: `/api/v1`

All authenticated endpoints use `Authorization: Bearer <access-token>`. OpenAPI at `/docs` is the executable schema source.

## Error envelope

Business and validation errors use:

```json
{
  "error": {
    "code": "INSPECTION_NOT_ASSIGNABLE",
    "message": "This inspection cannot be assigned in its current state.",
    "details": {}
  }
}
```

Stack traces are not returned to API clients.

## Authentication

### `POST /auth/login`

Request:

```json
{"email":"admin@example.com","password":"..."}
```

Response contains `accessToken`, `tokenType` and the authenticated user (`id`, `organizationId`, `email`, `fullName`, `role`).

### `GET /auth/me`

Returns the authenticated user resolved from the database.

## Inspectors

### `GET /inspectors`

Admin/reviewer organization-scoped listing. Query parameters: `search`, `active`, `page`, `pageSize`.

### `POST /inspectors`

Admin only. Creates an inspector user/profile in the admin's organization. Authentication credentials remain on `users`; inspector profiles do not duplicate passwords.

## Inspections

### `GET /inspections`

Server-side pagination and filtering:

- `page`, `pageSize`
- `status`
- `priority`
- `inspectorId`
- `search`
- `deadlineFrom`, `deadlineTo`
- `sortBy=createdAt|deadline|priority|status`
- `sortOrder=asc|desc`

Admins/reviewers receive only their organization. Inspectors receive only inspections with an active assignment to their own inspector profile.

### `GET /inspections/summary`

Admin/reviewer organization counts: total, draft, assigned, acknowledged, ready, cancelled, due today, overdue and high/critical priority.

### `POST /inspections`

Admin only. Creates a `DRAFT` inspection. Location latitude/longitude, radius and deadline are validated server-side.

### `GET /inspections/{inspectionId}`

Returns details and active assignment. Admin/reviewer responses include assignment history. Inspectors can retrieve only their own active assignments.

### `PATCH /inspections/{inspectionId}`

Admin only. Updates editable requirements. `status` is intentionally not an accepted request field.

### `POST /inspections/{inspectionId}/assign`

Admin only:

```json
{"inspectorId":"<uuid>"}
```

Requires `DRAFT`, same organization, an active inspector and no active assignment.

### `POST /inspections/{inspectionId}/reassign`

Admin only:

```json
{"inspectorId":"<uuid>","reason":"Original inspector unavailable"}
```

Preserves the previous assignment row and creates a new active row transactionally.

### `POST /inspections/{inspectionId}/acknowledge`

Only the active assigned inspector. `ASSIGNED → ACKNOWLEDGED`.

### `POST /inspections/{inspectionId}/ready`

Only the active assigned inspector. `ACKNOWLEDGED → READY`.

### `POST /inspections/{inspectionId}/cancel`

Admin only:

```json
{"reason":"Repair verification no longer required."}
```

Soft-cancels the inspection and closes any active assignment.
