# BarcodeCV Project Structure (Phase 2)

## Scope
This document defines the current target architecture for BarcodeCV and the maintainability boundaries for ongoing delivery work.

In scope:
- Backend and frontend layered separation
- Module boundaries and ownership
- Runtime data and control flow
- Config and environment strategy
- API contracts and responsibilities
- Test, logging, error, and performance strategy

Out of scope:
- Broad tech-stack replacement
- New unrelated features

---

## Top-Level Layout

```text
BarcodeCV/
├─ backend/                 # Python runtime domain logic + API + CLI
├─ frontend/                # Primary Next.js console
├─ config/                  # YAML runtime configuration
├─ tests/                   # Python unit and integration tests
├─ training/                # Optional model training utilities
├─ scripts/                 # Deployment and diagnostic scripts
├─ docs/                    # Specs, architecture, reports
├─ data/ logs/ output/      # Runtime artifacts
└─ requirements.txt
```

## Layered FE/BE Separation Principles

### Frontend (Presentation + BFF proxy)
- Canonical UI baseline: `frontend/`
- Owns: UI, user interactions, browser state, page composition.
- Does not own: barcode decoding algorithm, camera business logic, persistence.
- Communicates with backend via API routes in `frontend/src/app/api/*`.

### Backend (Domain + Infrastructure)
- Owns: detection and decoding pipeline, camera orchestration, DB persistence, scan and session lifecycle.
- Exposes stable HTTP contracts through FastAPI (`backend/api/main.py`).

### Infrastructure/Config
- Runtime behavior driven by `config/default.yaml` (+ override yaml).
- No hardcoded environment-specific constants in business modules.

---

## Backend Module Boundaries

- `backend/api/`: API entrypoint and contract layer (FastAPI routes + schemas)
- `backend/services/`: use-case orchestration for API calls
- `backend/services/detection_pipeline.py`: detection pipeline and image-level processing flow
- `backend/services/detection_records_service.py`: batch/object query and remark update flows
- `backend/services/detection_presenter.py`: backend DTO shaping for batches, objects, and summary output
- `backend/detection/`: OpenCV candidate detection + matching logic
- `backend/decoding/`: decoder abstraction + direct scanners (`pylibdmtx`, `zxing`)
- `backend/camera/`: camera source abstraction and device access
- `backend/database/`: SQLite manager + repositories
- `backend/calibration/`: focus/distance calibration flows
- `backend/utils/`: pure helpers (config/log/image/coord)
- `backend/pipeline.py`: CLI scan pipeline coordination
- `backend/main.py`: CLI entrypoint

Boundary rule: services can depend on detection, decoding, camera, and database; lower layers must not import the API layer.

---

## Data / Control Flow

### API flow
1. Client calls a frontend page or frontend API route.
2. Frontend API route forwards to backend FastAPI.
3. Backend route delegates to a service (`DetectionService`, `CameraService`, etc.).
4. Service performs detection and decoding + repository writes.
5. Presenter/helper layer normalizes output DTOs.
6. Response returns stable JSON contracts (`DetectionResponse`, etc.).

### CLI flow
1. `python -m backend.main --mode ...`
2. Load config and initialize camera, scanner, and repository.
3. `ScanPipeline.run_single_scan()` or continuous loop.
4. Persist scan records and output summary.

---

## Model / Inference / Decoding / Pre/Post Responsibilities

- Candidate localization: `backend/detection/opencv_datamatrix_detector.py`
- Decode execution: `backend/decoding/direct_scanner.py` (`PylibdmtxScanner`, `ZxingScanner`)
- Merge and dedup: detector/scanner composite layers
- Box detection and matching: `box_detector.py` + `spatial_matcher.py`
- Output shaping: `backend/services/detection_presenter.py`

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
- prefer `frontend/.env` / `.env.local` for backend base URL and deployment-specific settings

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
- bbox
- barcodeValue / barcodeType
- confidenceScore
- model metadata
- timestamps

---

## Test Strategy

- Unit tests by module domain under `tests/test_*`
- Decoder and detector behavior tests (including bbox conversion and dedup)
- Presenter/service tests for DTO shaping
- Repository and service tests
- Regression tests for previously observed issues (for example duplicate box detection)
- Frontend quality gate via `frontend` lint/build verification

---

## Logging / Error Handling

- Central logger setup via `backend/utils/logger.py`
- API translates domain failures to HTTP status codes
- Camera and detection services log warnings for recoverable faults and errors for hard failures
- Diagnostics endpoint available: `/api/cameras/debug`

---

## Acceptance Criteria

- Backend and primary frontend (`frontend`) run with documented entrypoints
- API contracts unchanged or backward compatible
- Tests pass on supported environment
- Frontend quality gates remain green
- Architecture docs stay aligned with the current canonical frontend
