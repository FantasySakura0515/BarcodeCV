# Migration Plan (Phase 2)

## Objectives
1. Consolidate runtime code under `backend/` and `frontend/` boundaries.
2. Preserve API behavior while improving maintainability.
3. Integrate branch improvements selectively with stability-first policy.

---

## Migration Scope
In scope:
- Directory/module organization refinement
- Import/entrypoint/config consistency fixes
- Detection accuracy/performance bug fixes
- Tests/regression/benchmark additions
- Architecture/reporting docs

Out of scope:
- New product features unrelated to barcode/datamatrix pipeline
- Full framework rewrites

---

## Baseline Observations
- Repo already migrated from `src/` to `backend/` in feature branches.
- Frontend exists as first-class directory and uses backend API proxy routes.
- Core remaining technical debt: detector edge-case stability + branch integration documentation completeness.

---

## Step Plan

### Step A: Inventory + branch diff mapping
- Enumerate all modules/entrypoints/config/dependencies
- Build branch comparison table with keep/drop rationale

### Step B: Documentation-first gate
- Create architecture docs in `docs/architecture/` before code changes

### Step C: Integration artifact generation
- Produce structure/module mapping + risk/rollback matrix

### Step D: Code migration/integration execution
- Apply minimal, targeted code changes only where required
- Keep API contracts stable

### Step E: Validation
- Run tests after major changes
- Run benchmark/regression scripts for optimization claims

### Step F: Final report
- `docs/reports/<timestamp>-migration-report.md`

---

## FE/BE Separation Rules During Migration
- Frontend cannot call DB/camera internals directly.
- Backend cannot depend on frontend code.
- All cross-layer integration via HTTP API contracts.

---

## Config & Entry Point Strategy
- Backend API: `python -m backend.api`
- Backend CLI: `python -m backend.main --mode ...`
- Frontend: `npm run dev` in `frontend/`
- Runtime config source of truth: `config/default.yaml`

---

## Test & Quality Gates
- Unit tests: `./.venv/Scripts/python.exe -m pytest -q`
- Additional regression tests for bugfixes
- Benchmark evidence required for any performance claim

---

## Logging & Error Handling Requirements
- Preserve structured warnings for camera/detector failures
- No swallowed exceptions without explicit fallback handling
- API routes return meaningful HTTP 4xx/5xx mapping

---

## Acceptance Criteria
- Architecture docs completed before code modifications
- Branch integration rationale documented for all local branches
- Codebase runnable for backend/frontend entrypoints
- Tests passing in project venv
- Final report includes migration log + benchmark/regression evidence
