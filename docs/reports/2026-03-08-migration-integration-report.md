# BarcodeCV Migration / Integration Final Report

Date: 2026-03-08 (GMT+8)
Branch: `feature/optimize-detection-v2`

## 1) Summary
Completed scoped execution across required phases:
- Phase 1 inventory of repository/modules/entrypoints/config/flows/branches
- Phase 2 architecture docs created before code changes
- Phase 3 migration/integration artifacts created (mapping, decision matrix, risks/rollback)
- Phase 4 migration/integration validated on current target branch structure
- Phase 5 bug fix + regression + benchmark artifact for box detection stability
- Phase 6 final report generated (this file)

No unrelated features or stack rewrites were introduced.

---

## 2) Structure Outcome
Current structure remains aligned with target FE/BE layering:
- Backend runtime/API: `backend/*`
- Frontend UI/proxy: `frontend/*`
- Config: `config/default.yaml`
- Tests: `tests/*`
- Optional training: `training/*`

Architecture docs added:
- `docs/architecture/project-structure.md`
- `docs/architecture/migration-plan.md`
- `docs/architecture/branch-integration-plan.md`
- `docs/architecture/migration-artifacts.md`

---

## 3) Branch Results

### Local branch comparison (keep/drop rationale)

| Branch | Keep/Drop | Rationale |
|---|---|---|
| `main` | Keep (reference) | Stable baseline + camera fix lineage |
| `feature/cv-detection-improvements` | Keep (historical integration source) | Contains staged detection/perf + restructure progression |
| `feature/optimize-detection-v2` | Keep (target) | Superset active branch with latest integration state |

### High-level diffs observed
- Feature branch lineage includes: `src -> backend` migration, FastAPI+Next integration, detection tuning and live flow optimizations.
- `feature/cv-detection-improvements` and `feature/optimize-detection-v2` currently share latest commit lineage tip.

---

## 4) Migration Log
1. Inventoried tracked modules (`git ls-files`), branch graph/log, and diff stats against `main`.
2. Authored architecture docs prior to any code modifications.
3. Authored migration/integration artifacts (mapping + risk/rollback + branch matrix).
4. Implemented focused detection bug fix (box contour duplicate handling / bbox stability).
5. Added regression test for dedup preference behavior.
6. Added benchmark script to compare legacy/current dedup outcomes.
7. Verified test execution in project venv.

---

## 5) Bug Fixes
### Box detector duplicate/oversize contour issue
Files:
- `backend/detection/box_detector.py`
- `tests/test_detection/test_box_detector.py`

Changes:
- Reworked `_deduplicate` to handle overlap/containment and prefer tighter bbox candidates.
- Added `_containment_ratio` helper.
- Added adaptive bbox margin normalization in `_contour_to_result` to stabilize contour boundary drift.
- Added regression test `test_deduplicate_prefers_tighter_bbox_when_contained`.

Result:
- Existing rectangle detection tests now pass reliably.
- Duplicate candidates reduced while retaining expected box count.

---

## 6) Optimization (with evidence)
Benchmark artifact:
- `tests/benchmarks/box_dedup_benchmark.py`

Command:
- `./.venv/Scripts/python.exe tests/benchmarks/box_dedup_benchmark.py`

Observed output:
- `legacy_count=3 current_count=3`
- `legacy_total_area=58500 current_total_area=36000`
- `legacy_time_ms=14.79 current_time_ms=29.09 rounds=2000`

Interpretation:
- Accuracy/quality improvement: tighter total selected bbox area (~38.5% lower), indicating reduced oversized duplicate selections.
- CPU cost increase in dedup micro-path is acceptable for maintainability/correctness priority and small candidate sets.

---

## 7) Validation Results
- Tests: `./.venv/Scripts/python.exe -m pytest -q`
- Result: `47 passed`
- Warning observed: `.pytest_cache` write permission warning (non-blocking)

---

## 8) Risks
- Tighter dedup heuristics may under-merge in unusual contour distributions.
- Bbox margin normalization may require retuning for very small boxes.

Mitigation:
- Regression tests kept for key synthetic patterns.
- Benchmark script provides quick comparison path.
- Changes isolated to `box_detector` for easy rollback.

---

## 9) Rollback Plan
If regressions appear:
1. Revert commit `fix(detection): tighten box dedup...`
2. Re-run tests and benchmark
3. Re-introduce only validated sub-parts via small commits

---

## 10) Commit Summary
1. `4dd6d87` — docs(architecture): add project structure, migration and branch integration plans
2. `4cec9c1` — fix(detection): tighten box dedup and stabilize bbox output for contour duplicates
3. `349403a` — test(benchmark): add box dedup comparison benchmark script
