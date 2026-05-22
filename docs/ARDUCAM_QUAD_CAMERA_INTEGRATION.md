# Arducam B0402 CamArray 整合與 Debug 指南

> 日期: 2026-04-03  
> 目標硬體: Arducam 64MP Quad Camera Kit `B0402` + Raspberry Pi 5  
> 目標架構: `dual-channel aggregated` 單相機主線

---

## 1. 結論

這組 `B0402` 不是一般的四顆獨立 CSI 相機。

- 它是 `CamArray HAT`，會把多顆 sensor 合成成 **1 顆 camera device**
- Raspberry Pi / libcamera / Picamera2 看到的是 **單一 camera_num=0**
- BarcodeCV 現在的主線也已改成 **單相機架構**
- 部署時固定建議使用 `dual-channel mode`，不再使用 `global/local` 雙鏡頭模型

這代表目前系統的正確心智模型是：

`B0402 dual mode -> 1 個聚合影像來源 -> BarcodeCV main camera`

---

## 2. 官方模式與我們採用的模式

Arducam 官方文件指出，B0402 支援：

- `single-channel`
- `dual-channel`
- `quad-channel`

而且官方明確說明，Pi 會把整組 kit 視為 **一顆相機**。

### 我們採用的主線

- 模式: `dual-channel`
- 佈局: `horizontal`
- 啟用通道: `[0, 1]`
- Picamera2: `camera_num=0`

### 為什麼選 dual mode

- 最符合目前實際需求: 只需要兩顆鏡頭
- 不需要保留四分割畫面再忽略其中兩格
- 不需要在 app 裡維護 `global/local` 雙來源同步
- 保留 CamArray 的同步輸出特性
- 仍然維持單一 Picamera2 device，整合最單純

---

## 3. 硬體模式切換

BarcodeCV **不會** 在 Python 程式裡自動切換 B0402 模式。  
模式切換屬於部署 / 維運步驟，請在 Pi 上先切好再啟動系統。

### dual mode: 通道 0 + 1

```bash
sudo i2cset -y 10 0x24 0x24 0x01
```

### dual mode: 通道 2 + 3

```bash
sudo i2cset -y 10 0x24 0x24 0x11
```

### quad mode（官方預設，非本專案主線）

```bash
sudo i2cset -y 10 0x24 0x24 0x00
```

### single channel 參考

```bash
sudo i2cset -y 10 0x24 0x24 0x02  # channel 0
sudo i2cset -y 10 0x24 0x24 0x12  # channel 1
sudo i2cset -y 10 0x24 0x24 0x22  # channel 2
sudo i2cset -y 10 0x24 0x24 0x32  # channel 3
```

> 注意: 以上模式值來自 Arducam 的 `64MP-AF Synchronized Quad-Camera Kit` 官方快速開始文件。  
> Pi 5 上使用的是 I2C bus `10`，不是 `6`。

---

## 4. Raspberry Pi 上的安裝步驟

### 4.1 安裝 Arducam 驅動

```bash
cd ~
wget -O install_pivariety_pkgs.sh https://github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver/releases/download/install_script/install_pivariety_pkgs.sh
chmod +x install_pivariety_pkgs.sh

./install_pivariety_pkgs.sh -p libcamera_dev
./install_pivariety_pkgs.sh -p libcamera_apps
./install_pivariety_pkgs.sh -p 64mp_pi_hawk_eye_kernel_driver
```

### 4.2 設定 B0402 為 dual mode

```bash
sudo i2cset -y 10 0x24 0x24 0x01
```

### 4.3 重新開機

```bash
sudo reboot
```

### 4.4 驗證系統只看到 1 顆相機

```bash
rpicam-hello --list-cameras
```

預期結果：

- 只看到 `1` 顆 camera
- 通常是 `camera 0`
- **不要**期待出現 2 顆或 4 顆 camera

如果系統列出多顆 camera，那通常代表你接的不是 B0402 CamArray 主線，或硬體模式 / overlay 判斷有誤。

---

## 5. BarcodeCV 現在的配置方式

`config/default.yaml` 已改成單鏡頭：

```yaml
cameras:
  main:
    type: "arducam"
    camera_num: 0
    width: 1920
    height: 1080
    allow_opencv_fallback: false
    role: "aggregated"

camarray:
  mode: "dual"
  layout: "horizontal"
  active_channels: [0, 1]
```

### 重點

- `cameras.main` 是唯一主鏡頭
- `camera_num` 固定走 `0`
- `camarray` 區塊只是描述部署事實，不會主動下 I2C 指令
- `allow_opencv_fallback` 預設維持 `false`，因為這是 CSI 相機，不是 USB/UVC 裝置

---

## 6. 程式架構上的變更

目前 repo 已完成以下重構：

- 移除 `global/local` 雙鏡頭架構
- `CameraManager` 改成單一 `main` 相機
- `ScanPipeline` 改成單次抓取一張聚合畫面後直接：
  - preprocess
  - box detect
  - decode
  - persist
- CLI `preview` / `single` / `continuous` / `calibration` 全部改成單畫面流程
- legacy DB 欄位：
  - `wide_image_path`
  - `closeup_image_path`
  已整併成 `frame_image_path`
- legacy `image_source=global/local` 已遷移成 `image_source=main`

---

## 7. 為什麼不需要自訂 CamArraySource

在目前主線下，不需要額外新增 `ArducamCamArraySource`。

原因是：

- B0402 在 dual mode 下，對 Picamera2 來說仍然是 **單一 camera device**
- 我們不再把聚合畫面拆回 `global/local`
- 所以直接使用現有 `PiCameraSource(camera_num=0)` 即可

換句話說，CamArray 的多通道控制由硬體 / Arducam HAT 處理；  
BarcodeCV 只負責讀取最終輸出的單一聚合畫面。

---

## 8. 建議解析度

由於 B0402 dual mode 本質上是兩路合成，因此不建議一開始就追求最高解析度。

### 建議起點

- `1920x1080`
- 或 `2312x1736`

### 使用建議

- `1920x1080`
  - 最適合先把 preview、串流與即時辨識跑穩
- `2312x1736`
  - 適合需要更高條碼細節時再往上調
- `9152x6944`
  - 不適合作為即時主線

---

## 9. Debug 流程

### 9.1 先驗證驅動與模式，不要先怪 app

```bash
rpicam-hello --list-cameras
python3 -c "from picamera2 import Picamera2; print(Picamera2.global_camera_info())"
python3 scripts/diagnose_camera.py
```

### 9.2 預期現象

- `list-cameras` 有且只有 1 顆 camera
- `global_camera_info()` 至少列出 `Num=0`
- `scripts/diagnose_camera.py` 能成功打開 `camera 0`

### 9.3 常見異常與對應

#### A. `No cameras available`

優先檢查：

- CSI 排線方向
- HAT 是否正確上電
- Arducam 驅動是否已安裝
- 是否已切到 dual mode

重新下模式指令：

```bash
sudo i2cset -y 10 0x24 0x24 0x01
```

然後再跑：

```bash
rpicam-hello --list-cameras
```

#### B. Picamera2 import 失敗

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-libcamera libcamera-apps v4l-utils
```

若使用 venv：

```bash
rm -rf .venv
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### C. 可以列出相機，但 BarcodeCV 還是失敗

檢查：

- `config/default.yaml` 是否仍指到 `cameras.main.camera_num: 0`
- `cameras.main.type` 是否為 `arducam`
- `allow_opencv_fallback` 是否誤開成 `true`

#### D. 看到的畫面不是 dual，而像 quad

代表 HAT 還停在四通道模式。重新執行：

```bash
sudo i2cset -y 10 0x24 0x24 0x01
```

如果你實際接的是第 2、3 顆，改用：

```bash
sudo i2cset -y 10 0x24 0x24 0x11
```

---

## 10. 目前不做的事

以下項目不在現階段主線內：

- 在 app 內自動切換 CamArray 硬體模式
- 維持 `global/local` 兩路邏輯 camera
- 把 dual mode 畫面再切成兩塊分開掃描
- 把 quad mode 當作正式部署主線

如果未來要做左右子畫面裁切，那會是新的處理策略，不是目前這版 runtime 的預設行為。

---

## 11. 參考資料

- Arducam 64MP Quad Camera Kit product page
- Arducam `64MP-AF Synchronized Quad-Camera Kit` 快速開始 PDF
- Arducam Pivariety driver installer
- Raspberry Pi Picamera2 / libcamera 文件
