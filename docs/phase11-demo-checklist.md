# Phase 11 Demo & Accessibility Checklist

This checklist is for the final SiteProof SIH demo and release rehearsal. It does not create or alter verification results.

## Pre-demo system check

- `phase11-final-polish` is deployed from a clean working tree.
- PostgreSQL is healthy and Alembic reports `0010_phase10_advanced_signals (head)`.
- `/health` reports the API online and receipt signing ready.
- Web dashboard loads without console-blocking errors.
- Android device can reach the backend over the selected test network.
- At least one known VERIFIED inspection, one FLAGGED/attention case, and one receipt-history case are available.

## Primary demo path

1. Sign in to the SiteProof control desk.
2. Show the Trust & evidence dashboard and explain that current counts use the latest immutable result per inspection.
3. Open Reviewer workspace.
4. Filter current decisions by verdict, inspector, site, review state, or verification date.
5. Select a site on the map and open its evidence record.
6. Show the automated verdict, score, confidence, engine/policy version, and hard-rule state.
7. Show captured video evidence and its stored SHA-256/hash-verification state.
8. Show sensor challenge, visual-motion, cross-signal, advanced-security, and advanced-signal evidence.
9. Open the signed receipt and validate its signature state.
10. Show receipt history and explain that SUPERSEDED receipts remain preserved rather than rewritten.
11. If appropriate, demonstrate a human reviewer decision as a separate audit action; do not describe it as changing the automated verdict.
12. Return to the dashboard and show the operational summary.

## Test 10 regression proof

For the known Test 10 case, confirm the current result is produced by `verification-engine-v1.1`, is VERIFIED, has no erroneous high-confidence fusion mismatch hard override, and displays the newest signed receipt while the earlier v1.0 FLAGGED receipt remains SUPERSEDED in history.

Do not hard-code Test 10 identifiers into UI code or seed scripts. Display whatever identifiers are stored by the real backend.

## Failure-state rehearsal

- Disable network connectivity and confirm the global offline banner appears without destroying the current screen.
- Restore connectivity and confirm data can refresh.
- Exercise an empty filter result in Reviewer workspace and Inspections.
- Confirm backend/API errors show a readable retry action instead of a blank screen.
- Confirm unavailable evidence video shows an explicit unavailable state.
- Confirm a failed protected-video load can be retried.
- Confirm a top-level rendering error is recoverable through the application reload screen.

## Accessibility smoke test

- Keyboard-only: use the skip link, primary navigation, filters, evidence links, reviewer actions, pagination, and video controls.
- Confirm visible focus is present on interactive controls.
- Confirm verdict meaning is expressed in text and not color alone.
- Confirm minimum control targets remain usable on narrow/mobile layouts.
- Confirm inspection tables have a caption and scoped column headers.
- Confirm dynamic loading/error states use status/alert semantics where appropriate.
- Enable reduced-motion preference and confirm the UI remains usable without transition dependence.
- Test a narrow viewport (approximately 360–390 px) and a tablet viewport before the demo.

## Demo integrity rules

- Never delete or rewrite a historical receipt to make the demo cleaner.
- Never change an automated verdict through reviewer UI; reviewer decisions remain separate audit events.
- Never reset the production/demo database immediately before the presentation unless a verified backup and restore plan exists.
- Do not claim a signal was captured if the UI reports it unavailable or inconclusive.
