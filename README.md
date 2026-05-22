# BarcodeCV

**Language:** [English](#english) | [繁體中文](#繁體中文)

---

## English

BarcodeCV is a full-stack barcode recognition system for DataMatrix scanning on Raspberry Pi 5 and Arducam CamArray. It provides an operator console for image upload, live camera preview, barcode detection, batch review, and object-level inspection, backed by a FastAPI service and SQLite persistence.

The project focuses on a practical factory-floor workflow: capture images from camera hardware, detect and decode barcodes, store the results, and make each scan traceable through a web interface.

### What It Does

- Detects and decodes DataMatrix barcodes from uploaded images or live camera capture.
- Shows bounding boxes, recognition metadata, batch records, and object details in a browser-based console.
- Persists scan history, devices, batches, objects, and runtime settings in SQLite.
- Separates frontend UI, backend services, camera access, detection logic, decoding, and database layers.
- Includes deployment and diagnostic scripts for Raspberry Pi camera environments.

### Key Engineering Work

- Built a FastAPI backend with clear service boundaries for detection, camera control, model state, records, and statistics.
- Implemented a Next.js + TypeScript operator console for daily scanning and result review workflows.
- Designed SQLite repositories and schema documentation for traceable scan records.
- Added camera diagnostics for Raspberry Pi / Arducam setup, including fallback checks and actionable error paths.
- Organized verification scripts for frontend lint/build checks and backend regression tests.
- Documented system structure, API behavior, database schema, and delivery checks.

### Tech Stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Backend:** Python, FastAPI, OpenCV
- **Database:** SQLite
- **Hardware:** Raspberry Pi 5, Arducam CamArray
- **Workflow:** DataMatrix detection, decoding, matching, result review
- **Quality:** ESLint, Next.js build, pytest, verification scripts

### Core Screens and Workflows

- Image detection workspace
- Live camera preview and capture detection
- Batch history and batch detail pages
- Object detail pages with barcode metadata
- Model status and runtime configuration views
- Camera availability and troubleshooting diagnostics

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

Run the repository verification script:

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

[Back to language selector](#barcodecv)

---

## 繁體中文

BarcodeCV 是一套針對 Raspberry Pi 5 與 Arducam CamArray 建立的全端 DataMatrix 條碼辨識系統。系統提供瀏覽器操作介面，可進行影像上傳、即時鏡頭預覽、條碼偵測、批次紀錄查詢與物件層級檢視，後端由 FastAPI 服務與 SQLite 紀錄持久化支撐。

這個專案聚焦在實際產線情境：從鏡頭取得影像、偵測並解碼條碼、保存辨識結果，並讓每一次掃描都能在網頁介面中追蹤與複核。

### 系統功能

- 從上傳影像或即時鏡頭擷取中偵測並解碼 DataMatrix 條碼。
- 在網頁操作介面顯示 bounding boxes、辨識 metadata、批次紀錄與物件細節。
- 使用 SQLite 保存掃描歷史、設備、批次、物件與 runtime 設定。
- 清楚分離前端 UI、後端服務、鏡頭存取、偵測邏輯、解碼流程與資料庫層。
- 提供 Raspberry Pi 鏡頭環境的部署與診斷腳本。

### 工程重點

- 建立 FastAPI 後端，將偵測、鏡頭控制、模型狀態、紀錄查詢與統計摘要切成清楚的服務邊界。
- 實作 Next.js + TypeScript 操作介面，支援日常掃描與結果複核流程。
- 設計 SQLite repository 與資料表文件，讓掃描紀錄可追蹤、可查詢。
- 加入 Raspberry Pi / Arducam 診斷工具，提供 fallback checks 與可行的錯誤處理方向。
- 整理前端 lint/build 與後端 regression tests 的驗證腳本。
- 補齊系統架構、API 行為、資料庫 schema 與交付檢查文件。

### 技術棧

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Backend:** Python, FastAPI, OpenCV
- **Database:** SQLite
- **Hardware:** Raspberry Pi 5, Arducam CamArray
- **Workflow:** DataMatrix detection, decoding, matching, result review
- **Quality:** ESLint, Next.js build, pytest, verification scripts

### 主要畫面與流程

- 單張影像辨識工作台
- 即時鏡頭預覽與擷取辨識
- 批次歷史與批次詳細頁
- 物件詳細頁與條碼 metadata
- 模型狀態與 runtime configuration 檢視
- 鏡頭可用性檢查與問題診斷

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

執行 repo-level 驗證：

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

[回到語言選單](#barcodecv)
