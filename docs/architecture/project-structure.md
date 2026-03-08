# BarcodeCV Project Structure (Phase 2)

## Scope
This document defines the **current target architecture** for BarcodeCV and the maintainability boundaries for migration/integration work.

In scope:
- Backend/Frontend layered separation
- Module boundaries and ownership
- Runtime data/control flow
- Config/env strategy
- API contracts and responsibilities
- Test/logging/error/performance strategy

Out of scope:
- Broad tech-stack replacement
- New unrelated features

---

## Top-Level Layout

```text
BarcodeCV/
├─ backend/                 # Python runtime domain logic + API + CLI
├─ frontend/                # Next.js UI + BFF proxy routes
├─ config/                  # YAML runtime configuration
├─ tests/                   # Python unit/integration tests
├─ training/                # Optional model training utilities
├─ scripts/                 # Deployment/diagnostic scripts
├─ docs/                    # Specs, architecture, reports
├─ data/ logs/ output/      # Runtime artifacts
└─ requirements.txt
```

## Layered FE/BE Separation Principles

### Frontend (Presentation + BFF proxy)
- Owns: UI, user interactions, browser state, page composition.
- Does not own: barcode decoding algorithm, camera business logic, persistence.
- Communicates with backend via API routes in `frontend/src/app/api/*` (proxy/adaptation).

### Backend (Domain + Infrastructure)
- Owns: detection/decoding pipeline, camera orchestration, DB persistence, scan/session lifecycle.
- Exposes stable HTTP contracts through FastAPI (`backend/api/main.py`).

### Infrastructure/Config
- Runtime behavior driven by `config/default.yaml` (+ override yaml).
- No hardcoded environment-specific constants in business modules.

---

## Backend Module Boundaries

- `backend/api/`: API entrypoint and contract layer (FastAPI routes + schemas)
- `backend/services/`: use-case orchestration for API calls
- `backend/detection/`: OpenCV candidate detection + matching logic
- `backend/decoding/`: decoder abstraction + direct scanners (pylibdmtx/zxing)
- `backend/camera/`: camera source abstraction and device access
- `backend/database/`: SQLite manager + repositories
- `backend/calibration/`: focus/distance calibration flows
- `backend/utils/`: pure helpers (config/log/image/coord)
- `backend/pipeline.py`: CLI scan pipeline coordination
- `backend/main.py`: CLI entrypoint

Boundary rule: services can depend on detection/decoding/camera/database; lower layers must not import API layer.

---

## Data / Control Flow

## API flow
1. Client calls frontend page or frontend API route.
2. Frontend API route forwards to backend FastAPI.
3. Backend route delegates to service (`DetectionService`, `CameraService`, etc.).
4. Service performs detection/decoding + repository writes.
5. Response returns normalized DTO (`DetectionResponse`, etc.).

## CLI flow
1. `python -m backend.main --mode ...`
2. Load config and initialize camera/scanner/repository.
3. `ScanPipeline.run_single_scan()` or continuous loop.
4. Persist scan records and output summary.

---

## Model / Inference / Decoding / Pre/Post Responsibilities

- Candidate localization: `backend/detection/opencv_datamatrix_detector.py`
- Decode execution: `backend/decoding/direct_scanner.py` (`PylibdmtxScanner`, `ZxingScanner`)
- Merge and dedup: detector/scanner composite layers
- Box detection and matching: `box_detector.py` + `spatial_matcher.py`
- Post-processing/output shaping: `DetectionService._build_detection_objects`

---

## Config and Environment Strategy

Primary: `config/default.yaml`
- camera definitions
- decoding and detector thresholds
- API host/port/CORS
- database path and WAL
- logging and output dirs

Override mechanism:
- CLI `--config <path>` merges with defaults via `config_loader.load_config`

Frontend env:
- `frontend/.env.local` (from `.env.local.example`) for backend base URL.

---

## API I/O Contract Summary

Key endpoints:
- `GET /api/health`
- `GET /api/models`
- `POST /api/detections` (multipart image + modelType)
- `POST /api/live-preview-detection`
- `GET /api/cameras`
- `GET /api/cameras/{camera_id}/preview|stream|live-detection`
- `POST /api/cameras/{camera_id}/capture-detection`
- `GET /api/detections`, `GET /api/detections/{rid}`
- `GET/PATCH /api/objects/{bid}`
- `GET /api/stats/summary`

Output object contract includes:
- bbox, barcodeValue/barcodeType, confidenceScore, model metadata, timestamps.

---

## Test Strategy

- Unit tests by module domain under `tests/test_*`
- Decoder and detector behavior tests (including bbox conversion and dedup)
- Repository and service tests
- Regression tests for previously observed issues (e.g., duplicate box detection)
- Benchmark scripts for performance-sensitive paths (documented in reports)

---

## Logging / Error Handling

- Central logger setup via `backend/utils/logger.py`
- API translates domain failures to HTTP status codes
- Camera and detection services log warnings for recoverable faults and errors for hard failures
- Diagnostics endpoint available: `/api/cameras/debug`

---

## Performance Benchmark Plan

Primary metrics:
- live preview detection latency (ms/frame)
- candidate count and decode success rate
- false positives / duplicate boxes

Method:
- reproducible local benchmark script on fixed sample images
- report before/after deltas with environment notes

---

## Acceptance Criteria

- Backend and frontend run with documented entrypoints
- API contracts unchanged or backward compatible
- Tests pass on supported environment
- Branch integration decisions documented with keep/drop rationale
- Architecture docs and final migration report complete
