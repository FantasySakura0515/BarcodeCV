# BarcodeCV 專案結構設計規範

## 1. 目標

本專案結構應同時支援以下需求：

| 目標 | 說明 |
|---|---|
| 可維護 | 模組責任清楚，避免功能混雜 |
| 可測試 | 能區分單元、整合、端對端測試 |
| 可部署 | 可支援本機、訓練機、Raspberry Pi 5 |
| 可擴充 | 容易新增鏡頭、解碼器、偵測器、API |
| 可套件化 | 符合標準 Python 專案結構 |

---

## 2. 結構原則

| 原則 | 規範 |
|---|---|
| 依領域分層 | 以 `camera`、`detection`、`decoding`、`database`、`calibration` 拆分 |
| 入口分離 | CLI / 啟動程式不可與核心邏輯混在一起 |
| 硬體分離 | 硬體相依實作應與純邏輯分開 |
| 訓練分離 | `training/` 與 runtime 主程式分開管理 |
| 輸出分離 | `data/`、`logs/`、`output/`、`models/` 不與原始碼混放 |

---

## 3. 建議專案結構

```text
BarcodeCV/
├─ config/
├─ docs/
├─ data/
├─ logs/
├─ output/
├─ scripts/
├─ backend/
│  ├─ api/
│  ├─ camera/
│  ├─ calibration/
│  ├─ database/
│  ├─ decoding/
│  ├─ detection/
│  ├─ services/
│  ├─ utils/
│  ├─ main.py
│  └─ pipeline.py
├─ frontend/
│  └─ src/
│     ├─ app/
│     ├─ components/
│     ├─ lib/
│     ├─ stores/
│     └─ types/
├─ tests/
│  ├─ test_camera/
│  ├─ test_database/
│  ├─ test_decoding/
│  ├─ test_detection/
│  └─ test_pipeline/
├─ training/
├─ requirements.txt
└─ README.md
```

---

## 4. 目錄責任

| 目錄 | 用途 | 備註 |
|---|---|---|
| `backend/` | 主應用程式原始碼 | 所有核心邏輯集中於此 |
| `config/` | 環境設定檔 | `default`、`testing`、`pi5_deploy` |
| `tests/` | 測試 | 分 `unit` / `integration` / `e2e` |
| `training/` | 模型訓練與資料準備 | 與 runtime 分離 |
| `scripts/` | 操作型腳本 | 不放核心邏輯 |
| `models/` | 模型權重與匯出模型 | 應加入 `.gitignore` 管理大檔 |
| `data/` | DB、樣本資料、暫存資料 | 執行期資料 |
| `logs/` | 執行日誌 | 不進版控 |
| `output/` | 偵錯圖片、報表、匯出結果 | 不與 source 混放 |
| `docs/` | 架構、部署、規範文件 | 技術文件集中 |

---

## 5. `backend/` 模組分工

| 模組 | 職責 |
|---|---|
| `camera/` | 相機來源、管理、模擬鏡頭 |
| `calibration/` | 距離與焦距校正 |
| `database/` | DB 連線、資料模型、repository |
| `decoding/` | DataMatrix 解碼器與結果合併 |
| `detection/` | 盒體偵測、影像前處理、空間配對 |
| `services/` | 跨模組流程編排 |
| `utils/` | 設定、路徑、logger、影像工具 |

---

## 6. 檔案命名規範

| 類型 | 規範 | 範例 |
|---|---|---|
| 檔名 | `snake_case` | `spatial_matcher.py` |
| 類別 | `PascalCase` | `CameraManager` |
| 函式 / 變數 | `snake_case` | `load_config()` |
| 常數 | `UPPER_CASE` | `DEFAULT_TIMEOUT` |

避免使用：`misc.py`、`helper.py`、`common.py`、`test1.py`

---

## 7. 測試規範

| 層級 | 內容 | 是否依賴硬體 |
|---|---|---|
| `unit/` | 純邏輯測試 | 否 |
| `integration/` | 多模組整合測試 | 原則上否 |
| `e2e/` | 完整流程驗證 | 可是 |
| `fixtures/` | 測試圖片、假資料、測試設定 | 否 |

---

## 8. 設定與依賴規範

### 設定檔

| 檔案 | 用途 |
|---|---|
| `config/default.yaml` | 預設值 |
| `config/development.yaml` | 本地開發 |
| `config/testing.yaml` | 測試環境 |
| `config/pi5_deploy.yaml` | Raspberry Pi 5 部署 |

### 依賴檔

| 檔案 | 用途 |
|---|---|
| `requirements.txt` | 專案依賴清單，含 runtime 與必要開發依賴 |

---

## 9. 執行產物規範

| 類型 | 建議位置 | 是否進版控 |
|---|---|---|
| SQLite DB | `data/db/` | 否 |
| log | `logs/` | 否 |
| 偵錯圖片 | `output/images/` | 否 |
| 報表 | `output/reports/` | 視需求 |
| 訓練權重 | `models/trained/` | 否 |
| 匯出模型 | `models/exported/` | 視需求 |

---

## 10. 擴充規則

| 需求 | 應放位置 |
|---|---|
| 新鏡頭來源 | `backend/camera/` |
| 新解碼器 | `backend/decoding/` |
| 新偵測器 | `backend/detection/` |
| 新流程編排 | `backend/services/` |
| 新 API | `backend/api/` |
| 新背景工作 | `backend/jobs/` |

---

## 11. 最小落地建議

| 優先級 | 項目 |
|---|---|
| 高 | 維持 `backend/` 套件結構 |
| 高 | 建立 `tests/unit`、`tests/integration`、`tests/e2e` |
| 高 | 維持單一 `requirements.txt` 並明確管理依賴 |
| 中 | 建立 `data/`、`logs/`、`output/`、`models/` |
| 中 | 將流程拆入 `services/` |
| 中 | 建立 `pyproject.toml` |
| 低 | 補齊 CI、部署、架構文件 |

---

## 12. 結論

`BarcodeCV` 的結構設計應以 **套件化、分層化、可測試、可部署、可擴充** 為核心。

判斷標準只有五件事：

1. 功能是否有明確落點
2. 測試是否能獨立執行
3. 硬體與邏輯是否解耦
4. 訓練與 runtime 是否分離
5. 新功能加入時是否不需大改架構