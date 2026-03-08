# Migration & Integration Artifacts (Phase 3)

## 1) Structure Mapping Table

| Legacy/Conceptual Area | Current Path | Status | Notes |
|---|---|---|---|
| `src/*` runtime modules | `backend/*` | migrated | Namespace updated to `backend` imports |
| API app entry | `backend/api/main.py` + `backend/api/__main__.py` | active | `python -m backend.api` |
| CLI entry | `backend/main.py` | active | single/continuous/preview/calibration |
| FE app | `frontend/src/app/*` | active | Next.js app router |
| FE->BE bridge | `frontend/src/app/api/*` | active | proxy routing to backend |
| Runtime config | `config/default.yaml` (+ override) | active | central parameterization |

## 2) Module Mapping

| Capability | Modules |
|---|---|
| Camera abstraction/access | `backend/camera/base.py`, `picamera_source.py`, `opencv_source.py`, `camera_manager.py` |
| Detection candidate generation | `backend/detection/opencv_datamatrix_detector.py`, `box_detector.py` |
| Decode execution | `backend/decoding/direct_scanner.py`, `decoder.py`, `fallback_decoder.py` |
| Spatial association | `backend/detection/spatial_matcher.py` |
| Use-case orchestration | `backend/services/detection_service.py`, `camera_service.py`, `model_service.py`, `stats_service.py` |
| Persistence | `backend/database/db_manager.py`, `repository.py` |
| API contracts | `backend/api/schemas.py`, `backend/api/main.py` |

## 3) Branch Decision Matrix (All Local Branches)

| Branch | Keep/Drop | Rationale |
|---|---|---|
| `main` | Keep (reference) | Stable baseline and camera fix lineage |
| `feature/cv-detection-improvements` | Keep (historical integration source) | Contains intermediate optimization and structure migration commits |
| `feature/optimize-detection-v2` | Keep (target) | Latest integrated superset and active working branch |

## 4) Risk & Rollback Plan

| Risk | Impact | Mitigation | Rollback |
|---|---|---|---|
| Detector tuning increases false positives | Wrong box/DM matches | Add regression tests for synthetic rectangles + dedup behavior | Revert detector commit only |
| Performance tweak hurts decode recall | Missed DataMatrix | Keep benchmark + decode-count regression checks | Restore previous detector parameters/config |
| API contract drift | FE breakage | Keep response schema backward-compatible | Revert API-layer commit |
| Camera flow regression | Live preview/capture instability | Keep cache/lock logic isolated in service layer, smoke test endpoints | Revert camera service delta |

## 5) Rollout Sequence
1. Documentation gate complete
2. Small scoped code commits (bugfix, test, benchmark)
3. Test/benchmark verification
4. Final report and commit summary
