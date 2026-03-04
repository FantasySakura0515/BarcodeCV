# BarcodeCV

Raspberry Pi 5 雙鏡頭 DataMatrix 掃描系統。

在一個平面上放置數個貼有 DataMatrix 條碼的盒子，系統會自動掃描所有條碼、將每個盒子與其條碼配對，並對**沒有條碼的盒子發出警告**，提示操作者重新擺放。

---

## 使用情境

一個托盤上同時放置十幾個盒子，每個盒子頂面應貼有一張 DataMatrix 標籤。操作者將托盤推到鏡頭下方，系統一次掃描完畢，回報哪些盒子有標籤、哪些沒有。

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

## 硬體使用

| 元件 | 規格 |
|------|------|
| 主機 | Raspberry Pi 5（16GB，量產可嘗試降規格） |
| 鏡頭 × 2 | Pi Camera Module（CSI 排線，接 CAM0 / CAM1） |
| 儲存 | microSD 32GB+ 或 USB SSD |

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

## 輸出範例

### 單次掃描（`--mode single`）

```
=== Scan Summary: 5 boxes found ===
  [OK] Box #01 -> DMX-2024-A001  (pylibdmtx)
  [OK] Box #02 -> DMX-2024-A002  (zxing-cpp)
  [!!] Box #03 -> NO DATAMATRIX  (bbox=(312, 88, 480, 210)) - Please reposition the box!
  [OK] Box #04 -> DMX-2024-A004  (pylibdmtx)
  [OK] Box #05 -> DMX-2024-A005  (pylibdmtx)

  1 box needs repositioning.
```

### 持續掃描（`--mode continuous`）

```
--- Scan cycle 1 ---
  [OK] DMX-2024-A001 (via pylibdmtx)
  [OK] DMX-2024-A002 (via pylibdmtx)
  [!!] Box at bbox=(312, 88, 480, 210) has no DataMatrix — reposition needed
--- Scan cycle 2 ---
  ...
```

---

## 安裝

```bash
# 在 Raspberry Pi 5 上
git clone <repo-url> barcodeCV
cd barcodeCV

# 一鍵安裝（系統依賴 + Python 虛擬環境）
bash scripts/setup_pi5.sh

# 啟動虛擬環境
source venv/bin/activate
```

---

## 使用方式

### 單次掃描

```bash
python -m src.main --mode single
```

### 持續掃描

```bash
python -m src.main --mode continuous
```

每 2 秒自動掃描，按 `Ctrl+C` 停止。

### 距離校準

找出 Local 鏡頭的最佳拍攝距離：

```bash
python -m src.main --mode calibration
```

輸出範例：

```
=== CALIBRATION REPORT ===
Optimal distance: 120mm

   Distance    Sharpness    Decode OK     Time (ms)
--------------------------------------------------
     50mm        423.1          YES        120.3ms
    100mm       1102.5          YES         45.2ms
    120mm       1247.3          YES         38.7ms  <-- BEST
    150mm        891.0          YES         52.1ms
    200mm        312.4           NO          0.0ms
```

### 指定配置檔

```bash
python -m src.main --config config/pi5_deploy.yaml --mode single
```

---

## 專案架構

```
barcodeCV/
├── config/
│   ├── default.yaml                # 預設配置
│   └── pi5_deploy.yaml             # Pi 5 部署配置
│
├── src/
│   ├── main.py                     # CLI 入口
│   ├── pipeline.py                 # 掃描流程協調（Global→Local→配對→存檔）
│   │
│   ├── camera/
│   │   ├── base.py                 # Frame 資料結構 + 抽象介面
│   │   ├── picamera_source.py      # Picamera2 CSI 鏡頭實作
│   │   └── camera_manager.py       # 雙鏡頭管理
│   │
│   ├── decoding/
│   │   ├── direct_scanner.py       # 核心：整張影像掃描（偵測+解碼一步完成）
│   │   ├── decoder.py              # 解碼器抽象介面
│   │   ├── pylibdmtx_decoder.py    # pylibdmtx 實作
│   │   ├── zxing_decoder.py        # zxing-cpp 實作
│   │   └── fallback_decoder.py     # 複合解碼器（逐一嘗試）
│   │
│   ├── detection/
│   │   ├── box_detector.py         # OpenCV 盒子偵測（輪廓分析）
│   │   ├── spatial_matcher.py      # 盒子 ↔ DataMatrix 空間配對
│   │   ├── detector.py             # YOLO 模型封裝（optional）
│   │   └── preprocessor.py         # 影像前處理（CLAHE）
│   │
│   ├── database/
│   │   ├── db_manager.py           # SQLite 連線 + Schema
│   │   └── repository.py           # CRUD（ScanRepository + BoxRepository）
│   │
│   ├── calibration/
│   │   ├── distance_calibrator.py  # 最佳距離掃描
│   │   └── focus_scorer.py         # 影像清晰度評分（Laplacian / Tenengrad）
│   │
│   └── utils/
│       ├── config_loader.py        # YAML 載入 + deep merge
│       ├── coordinate_mapper.py    # Global ↔ Local 座標映射（Homography）
│       ├── image_utils.py          # 裁切 / 銳化 / 對比度增強
│       └── logger.py               # 日誌設定
│
├── training/                       # YOLO 訓練工具（optional，見下方說明）
├── tests/                          # 單元測試
├── scripts/
│   ├── setup_pi5.sh                # 一鍵安裝腳本
│   └── install_dependencies.sh
└── requirements.txt
```

---

## 主要設定

所有設定在 `config/default.yaml`，可用自訂 YAML 檔覆蓋特定欄位。

### 鏡頭

```yaml
cameras:
  global:
    camera_num: 0        # CSI CAM0
    width: 1920
    height: 1080
  local:
    camera_num: 1        # CSI CAM1
    width: 1920
    height: 1080
```

### 盒子偵測

```yaml
box_detection:
  enabled: true
  min_area: 5000         # 最小輪廓面積（px²），過濾雜訊
  max_area: 500000       # 最大輪廓面積
  canny_threshold1: 50
  canny_threshold2: 150
  morph_kernel_size: 5   # 膨脹核大小，連接斷裂邊緣
  approx_epsilon: 0.02   # 多邊形近似精度
  aspect_ratio_min: 0.3  # 長寬比過濾（排除細長噪點）
  aspect_ratio_max: 3.0
```

調整提示：
- 偵測到太多假盒子 → 增加 `min_area`，縮小 `aspect_ratio` 範圍
- 盒子被漏掉 → 降低 `canny_threshold1`，增加 `morph_kernel_size`

### 空間配對

```yaml
spatial_matching:
  overlap_threshold: 0.3   # 最低 IoU 才算配對成功
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

## 資料庫 Schema

```
scan_sessions
┌─────────────┐
│ id (UUID)   │─────────────────────────────────┐
│ started_at  │                                 │
│ ended_at    │                                 │
│ config      │                                 │
└─────────────┘                                 │
                                                │
scan_records                                    │
┌───────────────────────┐                       │
│ id (AUTO)             │◄──────────────────┐   │
│ session_id (FK)       │◄──────────────────┼───┘
│ decoded_content       │                   │
│ decode_success        │                   │
│ decoder_used          │                   │
│ bbox (x1,y1,x2,y2)   │                   │
│ image_source          │                   │
│ decode_time_ms        │                   │
└───────────────────────┘                   │
                                            │
box_records                                 │
┌───────────────────────┐                   │
│ id (AUTO)             │                   │
│ session_id (FK)       │───────────────────┘
│ status                │  "matched" | "missing_datamatrix"
│ box_bbox (x1,y1,x2,y2)│
│ box_area              │
│ scan_record_id (FK)   │──→ scan_records.id（若 matched）
│ decoded_content       │
│ overlap_ratio         │  IoU 值
└───────────────────────┘
```

---

## 技術棧

| 技術 | 用途 |
|------|------|
| Python 3.11+ | 主要語言 |
| Picamera2 | Pi Camera Module 驅動 |
| pylibdmtx | DataMatrix 偵測與解碼（主要） |
| zxing-cpp | DataMatrix 偵測與解碼（備援） |
| OpenCV | 盒子輪廓偵測、影像前處理 |
| SQLite3 | 結果持久化（WAL mode） |
| PyYAML | 配置管理 |

---

## 選配：YOLO 訓練

預設的 library 掃描模式對大多數場景已足夠。若遇到以下情況可考慮訓練 YOLO 模型：

- DataMatrix 非常小（< 5mm）且距離鏡頭較遠
- Library 持續遺漏肉眼可見的碼
- 需要在不解碼的情況下快速計算碼的數量

訓練工具已備於 `training/` 目錄，詳見 [training/README.md](training/README.md)。
