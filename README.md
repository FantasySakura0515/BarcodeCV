# BarcodeCV

BarcodeCV is a completed computer-vision barcode scanning system built for Raspberry Pi 5, Arducam CamArray, and DataMatrix recognition workflows. It combines a FastAPI backend, a Next.js operator console, SQLite persistence, camera diagnostics, and reproducible verification scripts into one maintainable full-stack project.

## Project Status

Completed portfolio-ready version.

The repository is organized for code review and handoff: runtime modules are separated from optional training utilities, API contracts are documented, and the frontend/backend verification commands are kept in the repo.

## Highlights

- Built an end-to-end DataMatrix scanning workflow for image upload, live preview, camera capture, result review, and object-level lookup.
- Designed a layered backend around detection, decoding, camera orchestration, persistence, and API presentation boundaries.
- Implemented a Next.js console for operators to inspect batches, review barcode objects, manage model state, and view scan summaries.
- Added SQLite-backed records for batches, objects, devices, settings, and detection history.
- Included Raspberry Pi and Arducam diagnostic scripts for deployment and hardware troubleshooting.
- Kept delivery quality visible through lint/build/test verification scripts and architecture documentation.

## Tech Stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Backend:** Python, FastAPI, OpenCV, SQLite
- **Hardware target:** Raspberry Pi 5 with Arducam CamArray
- **Recognition workflow:** DataMatrix candidate detection, decoding, matching, and result presentation
- **Quality gates:** ESLint, Next.js build, Python tests, repository verification scripts

## Core Features

- Single-image barcode recognition workspace
- Live camera preview and capture-based detection
- Batch history and object detail review
- Bounding-box visualization and detection metadata
- Model status and runtime configuration management
- Camera availability checks and deployment diagnostics
- Documented database schema and backend API contracts

## Repository Layout

```text
BarcodeCV/
├─ backend/                    # FastAPI runtime, services, detection, decoding, DB access
├─ frontend/                   # Next.js operator console
├─ config/                     # Runtime YAML configuration
├─ docs/                       # Architecture, API, database, and delivery notes
├─ scripts/                    # Startup, verification, camera diagnostics
├─ tests/                      # Python tests
├─ training/                   # Optional model training utilities
├─ data/ logs/ output/         # Runtime artifacts
└─ requirements.txt
```

## Quick Start

### 1. Backend Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Frontend Setup

```bash
cd frontend
npm install
cd ..
```

### 3. Start the Backend

```bash
python -m backend.api
```

Or on Windows PowerShell:

```powershell
scripts\start-backend.ps1
```

Backend defaults:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

### 4. Start the Frontend

```bash
cd frontend
npm run dev
```

Or on Windows PowerShell:

```powershell
scripts\start-frontend.ps1
```

Frontend default:

- Console: `http://localhost:3000`

## Verification

Run the repo-level verification scripts before handoff:

```powershell
scripts\verify.ps1
```

Frontend only:

```powershell
scripts\verify.ps1 -SkipBackend
```

Backend only:

```powershell
scripts\verify.ps1 -SkipFrontend
```

Manual frontend check:

```bash
cd frontend
npm run verify
```

## Documentation

- [Project structure](docs/architecture/project-structure.md)
- [Backend API spec](docs/BACKEND_SPEC.md)
- [Database schema](docs/database.md)
- [Delivery checklist](docs/delivery/release-checklist.md)

## Notes for Reviewers

This project is intended to show full-stack delivery in a hardware-adjacent computer-vision workflow: backend service boundaries, frontend operator experience, persistence design, deployment scripts, and maintainable documentation.
