# Delivery Checklist

BarcodeCV is only considered deliverable when all items below are true.

## Canonical Runtime

- Primary frontend is `frontend/`.
- Backend runtime entrypoint is `python -m backend.api`.
- Python commands use the repository virtual environment at `.venv/`.

## Verification

- Run `scripts/verify.ps1` before handoff.
- `frontend` passes `npm run verify`.
- Backend targeted tests pass.
- `.github/workflows/verify.yml` matches the local verification contract.
- There are no unreviewed runtime-only files checked in by accident.

## Repository Hygiene

- New work follows `.editorconfig`.
- User-facing pages and API messages do not contain placeholder, garbled, or boilerplate text.
- Transitional modules and one-off migration notes are removed once the migration is complete.
- New files have an obvious owner and purpose.

## Operational Readiness

- README points to the correct frontend, backend, and verification commands.
- Startup commands exist at repo root under `scripts/`.
- Architecture docs match the current canonical flow.
- Error paths produce actionable messages.

## Handoff Standard

- The system can be started from documented commands without tribal knowledge.
- Verification commands are reproducible on another machine with the same dependencies.
- Frontend and backend boundaries are understandable to a new engineer in under 15 minutes.
