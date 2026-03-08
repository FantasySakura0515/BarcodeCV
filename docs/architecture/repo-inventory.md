# Repo Inventory (Phase 1)

## Repository Snapshot
- Root contains backend, frontend, config, tests, training, scripts, docs, runtime artifact dirs.
- Active branch: `feature/optimize-detection-v2`

## Entrypoints
- Backend API: `backend/api/__main__.py` → `uvicorn backend.api.main:app`
- Backend CLI: `backend/main.py` (`single|continuous|preview|calibration`)
- Frontend: `frontend/package.json` scripts (`dev`, `build`, `start`, `lint`)

## Core Modules
- Camera: `backend/camera/*`
- Decoding: `backend/decoding/*`
- Detection: `backend/detection/*`
- Services: `backend/services/*`
- Database: `backend/database/*`
- API contract: `backend/api/schemas.py`

## Configs
- `config/default.yaml` (primary runtime config)
- `config/pi5_deploy.yaml` (deployment override)
- `frontend/.env.local.example` (frontend env template)

## Dependencies
- Python: `opencv-python-headless`, `pylibdmtx`, `zxing-cpp`, `fastapi`, `uvicorn`, `numpy`, etc. (see `requirements.txt`)
- Frontend: Next.js 16, React 19, Zustand, Tailwind 4, shadcn/radix ecosystem (see `frontend/package.json`)

## Training / Inference Flow
- Training utilities (optional): `training/train.py`, `training/evaluate.py`, `training/export_model.py`
- Runtime inference path currently OpenCV+decoder based:
  - detect candidate regions (`opencv_datamatrix_detector`)
  - decode via scanner composite (`pylibdmtx` + `zxing`)
  - merge and persist via `DetectionService`

## FE/BE Coupling
- Frontend API routes under `frontend/src/app/api/*` proxy backend endpoints.
- FE UI pages consume stable JSON contracts from backend schemas.
- No direct DB/camera coupling from frontend.

## Branches + High-level Diffs
- Local branches: `main`, `feature/cv-detection-improvements`, `feature/optimize-detection-v2`
- Feature branch lineage includes:
  - `src/` to `backend/` restructure
  - FastAPI + Next frontend integration
  - Detection/live-preview optimization commits
- `main` remains stable baseline with camera reliability fixes.
