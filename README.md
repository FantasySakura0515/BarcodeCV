# BarcodeCV

Raspberry Pi 5 雙鏡頭 DataMatrix 掃描系統，含 FastAPI 後端與 Next.js 前端。

在一個平面上放置數個貼有 DataMatrix 條碼的盒子，系統會自動掃描所有條碼、將每個盒子與其條碼配對，並對**沒有條碼的盒子發出警告**。

---

## 使用情境

倉儲、工廠出貨口，一個料盤或托盤上同時放置十幾個盒子，每個盒子頂面應貼有一張 DataMatrix 標籤。操作者將托盤推到鏡頭下方，系統一次掃描完畢，回報哪些盒子有標籤、哪些沒有。

```
┌──────────────────────────────────────┐
│          鏡頭視野（俯視）              │
│                                      │
│  ┌──────┐  ┌──────┐  ┌──────┐       │
│  │ DM   │  │      │  │ DM   │       │  ← 盒子
│  │ OK   │  │  !!  │  │ OK   │       │     DM = 有條碼
│  └──────┘  └──────┘  └──────┘       │     !! = 缺條碼 → 警告
│                                      │
│  ┌──────┐  ┌──────┐                 │
│  │ DM   │  │ DM   │                 │
│  │ OK   │  │ OK   │                 │
│  └──────┘  └──────┘                 │
└──────────────────────────────────────┘
```

---

## 硬體需求

| 元件 | 規格 |
|------|------|
| 主機 | Raspberry Pi 5（4GB 或 8GB） |
| 鏡頭 × 2 | Pi Camera Module（CSI 排線，接 CAM0 / CAM1） |
| 儲存 | microSD 32GB+ 或 USB SSD |

---

## 快速啟動

### 1. 安裝依賴

```bash
git clone <repo-url> BarcodeCV
cd BarcodeCV

# Python 依賴
pip install -r requirements.txt

# Node.js 依賴
cd frontend && npm install && cd ..
```

### 2. 啟動後端（FastAPI，Port 8000）

```bash
# 在專案根目錄執行
python -m backend.api
```

後端啟動後可訪問：
- API：`http://localhost:8000`
- 互動文件（Swagger UI）：`http://localhost:8000/docs`

### 3. 啟動前端（Next.js，Port 3000）

```bash
cd frontend

# 開發模式（含熱重載）
npm run dev

# 正式模式（需先 build）
npm run build && npm run start
```

前端啟動後訪問：`http://localhost:3000`

---

## 系統如何運作

### 兩顆鏡頭分工

| 鏡頭 | 角色 | 做什麼 |
|------|------|--------|
| **CAM0（廣角）** | Global | 拍攝整個平面，偵測所有盒子位置，初步掃描所有 DataMatrix |
| **CAM1（近距離）** | Local | 同一平面近拍，以更高解析度解碼每個條碼 |

兩顆鏡頭的掃描結果合併去重，Local 鏡頭優先（解析度較高）。

### 一次掃描的流程

```
CAM0 廣角拍攝
    │
    ├─→ 盒子偵測（OpenCV 邊緣偵測）→ [Box 1, Box 2, Box 3, ...]
    │
    └─→ DataMatrix 掃描（pylibdmtx + zxing-cpp）→ [DM-A, DM-B, ...]

CAM1 近距離拍攝
    │
    └─→ DataMatrix 掃描（pylibdmtx + zxing-cpp）→ [DM-A, DM-C, ...]

合併 DataMatrix 結果（Local 優先）
    │
    └─→ [DM-A, DM-B, DM-C]

空間配對（IoU + 中心點判斷）
    │
    ├─→ Box 1 ↔ DM-A  [matched]
    ├─→ Box 2 ↔ (無)  [missing_datamatrix] ← 警告
    └─→ Box 3 ↔ DM-B  [matched]

存入 SQLite
```

### 掃描引擎

不需要訓練任何 ML 模型，直接使用兩個開源解碼引擎：

| 引擎 | 角色 | 特性 |
|------|------|------|
| **pylibdmtx** | 主要 | 原生多碼偵測，穩定，可調 timeout |
| **zxing-cpp** | 備援 | C++ 後端，速度快，補捉 pylibdmtx 遺漏的碼 |

### 盒子偵測

使用 OpenCV 輪廓分析，不需要訓練資料：

1. Canny 邊緣偵測
2. 形態學膨脹（連接斷裂的邊緣）
3. 找外輪廓 → 多邊形近似 → 篩選四邊形
4. 面積、長寬比過濾（排除噪點）

適合外觀統一、背景對比明顯的盒子。

---

## CLI 掃描模式（不使用前端）

### 單次掃描

```bash
python -m backend.main --mode single
```

### 持續掃描

```bash
python -m backend.main --mode continuous
```

每 2 秒自動掃描，按 `Ctrl+C` 停止。

### 距離校準

```bash
python -m backend.main --mode calibration
```

### 指定配置檔

```bash
python -m backend.main --config config/pi5_deploy.yaml --mode single
```

---

## 專案架構

```
BarcodeCV/
├── config/
│   ├── default.yaml                # 預設配置
│   └── pi5_deploy.yaml             # Pi 5 部署配置
│
├── backend/                        # Python 後端
│   ├── main.py                     # CLI 入口
│   ├── pipeline.py                 # 掃描流程協調
│   │
│   ├── api/
│   │   ├── __main__.py             # API 啟動入口（python -m backend.api）
│   │   ├── main.py                 # FastAPI app 與路由
│   │   └── schemas.py              # Pydantic 資料結構
│   │
│   ├── camera/
│   │   ├── base.py                 # Frame 資料結構 + 抽象介面
│   │   ├── picamera_source.py      # Picamera2 CSI 鏡頭實作
│   │   └── camera_manager.py       # 雙鏡頭管理
│   │
│   ├── decoding/
│   │   ├── direct_scanner.py       # 整張影像掃描（偵測+解碼）
│   │   ├── decoder.py              # 解碼器抽象介面
│   │   ├── pylibdmtx_decoder.py    # pylibdmtx 實作
│   │   ├── zxing_decoder.py        # zxing-cpp 實作
│   │   └── fallback_decoder.py     # 複合解碼器（逐一嘗試）
│   │
│   ├── detection/
│   │   ├── box_detector.py         # OpenCV 盒子偵測（輪廓分析）
│   │   ├── opencv_datamatrix_detector.py  # OpenCV DataMatrix 偵測
│   │   ├── spatial_matcher.py      # 盒子 ↔ DataMatrix 空間配對
│   │   ├── detector.py             # YOLO 模型封裝（選配）
│   │   └── preprocessor.py         # 影像前處理（CLAHE）
│   │
│   ├── database/
│   │   ├── db_manager.py           # SQLite 連線 + Schema
│   │   └── repository.py           # CRUD（ScanRepository + BoxRepository）
│   │
│   ├── calibration/
│   │   ├── distance_calibrator.py  # 最佳距離掃描
│   │   └── focus_scorer.py         # 影像清晰度評分
│   │
│   ├── services/
│   │   ├── detection_service.py    # 偵測服務
│   │   ├── model_service.py        # 模型管理服務
│   │   └── stats_service.py        # 統計服務
│   │
│   └── utils/
│       ├── config_loader.py        # YAML 載入 + deep merge
│       ├── coordinate_mapper.py    # Global ↔ Local 座標映射
│       ├── image_utils.py          # 裁切 / 銳化 / 對比度增強
│       └── logger.py               # 日誌設定
│
├── frontend/                       # Next.js 前端
│   ├── src/
│   │   ├── app/                    # Next.js App Router 頁面
│   │   ├── components/             # UI 元件
│   │   ├── lib/                    # API 封裝、工具函式
│   │   ├── stores/                 # Zustand 狀態管理
│   │   └── types/                  # TypeScript 型別定義
│   └── package.json
│
├── tests/                          # Python 單元測試
├── training/                       # YOLO 訓練工具（選配）
├── scripts/
│   ├── setup_pi5.sh                # Pi 5 一鍵安裝腳本
│   └── install_dependencies.sh
├── data/                           # 執行期資料（SQLite DB）
├── logs/                           # 執行日誌
├── output/                         # 偵錯圖片、報表
└── requirements.txt
```

---

## 主要設定

所有設定在 `config/default.yaml`，可用自訂 YAML 檔覆蓋特定欄位。

### API

```yaml
api:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "http://localhost:3000"
```

### 鏡頭

```yaml
cameras:
  global:
    camera_num: 0        # CSI CAM0（廣角）
    width: 1920
    height: 1080
  local:
    camera_num: 1        # CSI CAM1（近距離）
    width: 1920
    height: 1080
```

### 盒子偵測

```yaml
box_detection:
  enabled: true
  min_area: 5000         # 最小輪廓面積（px²），過濾雜訊
  max_area: 500000
  canny_threshold1: 50
  canny_threshold2: 150
  morph_kernel_size: 5
  approx_epsilon: 0.02
  aspect_ratio_min: 0.3
  aspect_ratio_max: 3.0
```

### DataMatrix 解碼

```yaml
decoding:
  primary_decoder: "pylibdmtx"
  fallback_decoder: "zxing"
  merge_results: true
  pylibdmtx:
    timeout_ms: 5000       # 越長找越多碼，但越慢
    shrink: 1              # 1=原始解析度，2+=加速但可能漏碼
```

---

## 技術棧

### 後端

| 技術 | 用途 |
|------|------|
| Python 3.11+ | 主要語言 |
| FastAPI + uvicorn | REST API 伺服器 |
| Picamera2 | Pi Camera Module 驅動 |
| pylibdmtx | DataMatrix 解碼（主要） |
| zxing-cpp | DataMatrix 解碼（備援） |
| OpenCV | 盒子偵測、影像前處理 |
| SQLite3 | 結果持久化（WAL mode） |
| PyYAML | 配置管理 |

### 前端

| 技術 | 用途 |
|------|------|
| Next.js 16 | React 框架 |
| TypeScript | 型別安全 |
| Tailwind CSS | 樣式 |
| Zustand | 狀態管理 |
| shadcn/ui | UI 元件庫 |

---

## 執行測試

```bash
pytest tests/
```

---

## 選配：YOLO 訓練

預設的 library 掃描模式（pylibdmtx + zxing-cpp）對大多數場景已足夠。若遇到 DataMatrix 非常小或距離鏡頭較遠的情況，可考慮訓練 YOLO 模型。

訓練工具於 `training/` 目錄，詳見 [training/README.md](training/README.md)。
