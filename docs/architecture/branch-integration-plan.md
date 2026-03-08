# Branch Integration Plan (Phase 2)

## Local Branches
- `main`
- `feature/cv-detection-improvements`
- `feature/optimize-detection-v2` (current)

## High-Level Branch Diff Summary
- `feature/*` branches include major restructure (`src/ -> backend/`), FastAPI+Next integration, camera diagnostics, OpenCV DataMatrix enhancements.
- `main` contains Pi camera fixes (autofocus/video config/BGR channel correction) but not full FE/BE restructure.

---

## Integration Principles
1. Prefer **feature branch architecture** as target baseline (already includes new structure).
2. Keep only stable and maintainable improvements.
3. Avoid duplicate logic and dead paths after merge.
4. Resolve conflicts with correctness > novelty.

---

## Branch Decision Matrix

| Branch | Decision | Rationale | Action |
|---|---|---|---|
| main | Keep as reference; partial cherry-pick already reflected | Contains camera reliability fixes worth preserving | Verify parity with current `backend/camera/picamera_source.py` |
| feature/cv-detection-improvements | Keep (integrated) | Contains staged detection/perf fixes and restructure groundwork | Treat as upstream source of current feature lineage |
| feature/optimize-detection-v2 | Keep as integration target | Superset branch with latest optimization commits | Continue hardening/tests/docs on this branch |

---

## Conflict Handling Strategy
- File moves (`src/*` to `backend/*`): prefer destination path only.
- Detector tuning conflicts: prefer config-driven parameters over hardcoded constants.
- API route conflicts: preserve existing endpoint schema unless bugfix requires strict correction.

---

## Validation After Integration
- Run backend test suite in venv
- Smoke-check backend startup and frontend build lint path
- Verify camera/detection endpoints compile/import cleanly

---

## Acceptance Criteria
- Branch decisions documented and justified
- No unresolved structural conflict remnants
- Integrated branch remains testable/runnable
