# Inspection Lifecycle

## Phase 2 states

```text
DRAFT ──assign──> ASSIGNED ──acknowledge──> ACKNOWLEDGED ──mark ready──> READY
  │                    │                         │                 │
  └──── cancel ────────┴──────── cancel ─────────┴──── cancel ─────┘
                               ↓
                           CANCELLED
```

`CANCELLED` is terminal in Phase 2. There is no restore workflow.

## Who may transition

| Operation | Actor | Preconditions | Result |
|---|---|---|---|
| Create | Admin | authenticated organization admin | `DRAFT` |
| Assign | Admin | `DRAFT`, active same-organization inspector, no active assignment | `ASSIGNED` |
| Reassign | Admin | active assignment, not cancelled, different active same-org inspector | `ASSIGNED` |
| Acknowledge | Active assigned inspector | `ASSIGNED` | `ACKNOWLEDGED` |
| Mark ready | Active assigned inspector | `ACKNOWLEDGED` | `READY` |
| Cancel | Admin | not already cancelled | `CANCELLED` |

Clients cannot send arbitrary status values. Status changes are performed only by service methods behind dedicated API operations.

## Assignment history

An assignment is never deleted during reassignment:

```text
old ACTIVE assignment → REASSIGNED + unassigned_at + reason
new assignment        → ACTIVE
```

Cancellation marks any active assignment `CANCELLED` and records `unassigned_at` and the reason. A partial unique database index guarantees at most one `ACTIVE` assignment per inspection.

## Audit events

The backend creates these events server-side in the same business transaction:

- `INSPECTION_CREATED`
- `INSPECTION_UPDATED`
- `INSPECTION_ASSIGNED`
- `INSPECTION_REASSIGNED`
- `INSPECTION_ACKNOWLEDGED`
- `INSPECTION_READY`
- `INSPECTION_CANCELLED`

Each event records organization, actor, entity, action, timestamp and variable metadata such as reassignment/cancellation reasons.

## Overdue

Overdue is derived, not a status:

```text
deadline < now AND status != CANCELLED
```

This avoids creating unnecessary lifecycle states.

## Phase 3 boundary

`READY` is the hand-off point. Phase 2 intentionally stops there. `SESSION_STARTED` and later verification states are not active behaviors yet.
