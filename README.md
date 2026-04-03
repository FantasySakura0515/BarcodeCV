# BarcodeCV

BarcodeCV 是一套以 Raspberry Pi 5 與 Arducam CamArray 單聚合鏡頭為核心的 DataMatrix 掃描系統，包含：
- FastAPI 後端
- Next.js 前端工作台
- SQLite 結果持久化
- 單張辨識與即時辨識工作流

---

## 目前交付基線

- 主前端：`frontend/`
- 後端 API：`backend/api/main.py`
- 核心辨識服務：`backend/services/detection_service.py`
- 偵測管線：`backend/services/detection_pipeline.py`
- 結果查詢服務：`backend/services/detection_records_service.py`
- 輸出組裝層：`backend/services/detection_presenter.py`

---

## 快速啟動

### 1. 安裝依賴

```bash
git clone <repo-url> BarcodeCV
cd BarcodeCV

# Python environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Frontend dependencies
cd frontend
npm install
cd ..
```

### 2. 啟動後端

```bash
scripts\start-backend.ps1
```

後端預設：
- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

### 3. 啟動前端工作台

```bash
scripts\start-frontend.ps1
```

前端預設：
- Console: `http://localhost:3000`

---

## 品質驗證

### Frontend

```bash
scripts\verify.ps1 -SkipBackend
```

### Backend tests

```bash
scripts\verify.ps1 -SkipFrontend
```

注意：請優先使用 repo 內的 `.venv`，不要直接使用系統 Python，以避免版本不一致造成測試或型別語法失敗。

---

## 專案結構

```text
BarcodeCV/
├─ backend/                    # Python runtime, API, services, presenters
├─ config/                     # YAML runtime configuration
├─ docs/                       # Specs, architecture decisions, delivery docs
├─ frontend/                   # Primary Next.js console
├─ tests/                      # Python tests
├─ training/                   # Optional training utilities
├─ scripts/                    # Deployment and diagnostic scripts
├─ data/ logs/ output/         # Runtime artifacts
└─ requirements.txt
```

更多架構資訊可參考：
- `docs/architecture/project-structure.md`
- `docs/delivery/release-checklist.md`

---

## 核心能力

- 單張影像辨識工作台
- 即時鏡頭辨識與擷取
- 批次紀錄與批次複核
- 物件層級追蹤
- 模型版本與啟用狀態管理
- 條碼缺漏檢查與擺放提示

---

## 說明

目前 repo 的目標很直接：
把 BarcodeCV 收斂成一套架構清楚、前後端邊界明確、可交付、可持續維護的工業工具型系統。
