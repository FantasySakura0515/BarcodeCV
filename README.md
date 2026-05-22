# BarcodeCV

**Language:** [English](#english) | [繁體中文](#繁體中文)

---

## English

BarcodeCV is a completed computer-vision barcode scanning system built for Raspberry Pi 5, Arducam CamArray, and DataMatrix recognition workflows. It combines a FastAPI backend, a Next.js operator console, SQLite persistence, camera diagnostics, and reproducible verification scripts into one maintainable full-stack project.

### Project Status

Completed portfolio-ready version.

The repository is organized for code review and handoff: runtime modules are separated from optional training utilities, API contracts are documented, and the frontend/backend verification commands are kept in the repo.

### Highlights

- Built an end-to-end DataMatrix scanning workflow for image upload, live preview, camera capture, result review, and object-level lookup.
- Designed a layered backend around detection, decoding, camera orchestration, persistence, and API presentation boundaries.
- Implemented a Next.js console for operators to inspect batches, review barcode objects, manage model state, and view scan summaries.
- Added SQLite-backed records for batches, objects, devices, settings, and detection history.
- Included Raspberry Pi and Arducam diagnostic scripts for deployment and hardware troubleshooting.
- Kept delivery quality visible through lint/build/test verification scripts and architecture documentation.

### Tech Stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Backend:** Python, FastAPI, OpenCV, SQLite
- **Hardware target:** Raspberry Pi 5 with Arducam CamArray
- **Recognition workflow:** DataMatrix candidate detection, decoding, matching, and result presentation
- **Quality gates:** ESLint, Next.js build, Python tests, repository verification scripts

### Core Features

- Single-image barcode recognition workspace
- Live camera preview and capture-based detection
- Batch history and object detail review
- Bounding-box visualization and detection metadata
- Model status and runtime configuration management
- Camera availability checks and deployment diagnostics
- Documented database schema and backend API contracts

### Repository Layout

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

### Quick Start

Backend setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Frontend setup:

```bash
cd frontend
npm install
cd ..
```

Start the backend:

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

Start the frontend:

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

### Verification

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

### Documentation

- [Project structure](docs/architecture/project-structure.md)
- [Backend API spec](docs/BACKEND_SPEC.md)
- [Database schema](docs/database.md)
- [Delivery checklist](docs/delivery/release-checklist.md)

### Notes for Reviewers

This project is intended to show full-stack delivery in a hardware-adjacent computer-vision workflow: backend service boundaries, frontend operator experience, persistence design, deployment scripts, and maintainable documentation.

[Back to language selector](#barcodecv)

---

## 繁體中文

BarcodeCV 是一套已完成的電腦視覺條碼掃描系統，針對 Raspberry Pi 5、Arducam CamArray 與 DataMatrix 辨識流程設計。專案整合 FastAPI 後端、Next.js 操作介面、SQLite 紀錄持久化、鏡頭診斷工具與可重現的驗證腳本，呈現一個可維護、可交付的全端系統。

### 專案狀態

已完成，適合作為作品集與履歷展示專案。

此 repo 已整理成方便審閱與交接的狀態：runtime 模組與選用訓練工具分離、API contract 與資料庫結構有文件化，前後端驗證指令也保留在專案內。

### 專案亮點

- 建立完整 DataMatrix 掃描流程，包含影像上傳、即時預覽、鏡頭擷取、結果複核與物件層級查詢。
- 以分層架構整理後端，清楚切分 detection、decoding、camera orchestration、persistence 與 API presentation。
- 實作 Next.js 操作介面，支援批次檢視、條碼物件複核、模型狀態管理與掃描摘要。
- 使用 SQLite 保存批次、物件、設備、設定與偵測歷史紀錄。
- 提供 Raspberry Pi 與 Arducam 診斷腳本，方便部署與硬體問題排查。
- 透過 lint、build、Python tests 與架構文件讓交付品質可以被快速驗證。

### 技術棧

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Backend:** Python, FastAPI, OpenCV, SQLite
- **Hardware target:** Raspberry Pi 5 with Arducam CamArray
- **Recognition workflow:** DataMatrix candidate detection, decoding, matching, and result presentation
- **Quality gates:** ESLint, Next.js build, Python tests, repository verification scripts

### 核心功能

- 單張影像條碼辨識工作台
- 即時鏡頭預覽與擷取辨識
- 批次歷史紀錄與物件詳細檢視
- Bounding box 視覺化與偵測 metadata
- 模型狀態與 runtime configuration 管理
- 鏡頭可用性檢查與部署診斷
- 資料庫 schema 與後端 API contract 文件

### 專案結構

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

### 快速啟動

後端環境：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

前端環境：

```bash
cd frontend
npm install
cd ..
```

啟動後端：

```bash
python -m backend.api
```

或使用 Windows PowerShell：

```powershell
scripts\start-backend.ps1
```

後端預設位置：

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

啟動前端：

```bash
cd frontend
npm run dev
```

或使用 Windows PowerShell：

```powershell
scripts\start-frontend.ps1
```

前端預設位置：

- Console: `http://localhost:3000`

### 品質驗證

交付前可執行 repo-level 驗證：

```powershell
scripts\verify.ps1
```

只驗證前端：

```powershell
scripts\verify.ps1 -SkipBackend
```

只驗證後端：

```powershell
scripts\verify.ps1 -SkipFrontend
```

手動驗證前端：

```bash
cd frontend
npm run verify
```

### 文件

- [Project structure](docs/architecture/project-structure.md)
- [Backend API spec](docs/BACKEND_SPEC.md)
- [Database schema](docs/database.md)
- [Delivery checklist](docs/delivery/release-checklist.md)

### 給審閱者

此專案用來展示硬體整合情境下的全端開發能力：後端服務邊界、前端操作體驗、資料持久化設計、部署腳本與可維護文件。

[回到語言選單](#barcodecv)
