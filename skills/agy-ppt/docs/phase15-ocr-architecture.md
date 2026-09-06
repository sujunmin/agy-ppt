# Phase 15 OCR Provider Architecture & Default Engine Evaluation

本文件是 `agy-ppt` Phase 15（OCR Ingestion & Provider Architecture）的架構決策紀錄（Architecture Decision Record, ADR），定義提供者架構（Provider Architecture）、自備 OCR（Bring Your Own OCR, BYO-OCR）整合機制、預設本機引擎評估決策與工程實作路線圖。

---

## 1. 架構核心原則：BYO-OCR 與責任分離

`agy-ppt` 採用**提供者導向（Provider-based）**的 OCR 架構。系統**絕不**強制所有使用者只能綁定單一特定 OCR 引擎，而是定義標準化、可驗證的整合邊界：

```text
來源文件（掃描 PDF / 圖片）
        ↓
OCR 提供者解析（Provider Resolution）
        │
        ├── 使用者/專案顯式指定提供者（Custom / Enterprise / Cloud OCR）
        │        ↓
        │   驗證提供者契約（Provider Contract Validation）
        │        ↓
        │   執行提供者萃取
        │
        └── 未顯式指定提供者
                 ↓
           agy-ppt 預設本機提供者（Default Local Provider: Tesseract 5）
                 ↓
        標準化 OCR 證據（Normalized OCR Evidence）
                 ↓
        AGY 語意層（語意切分、論點對齊、數值校驗）
                 ↓
        Phase 12 來源接地（Frozen Grounding Architecture）
```

### 關鍵職責邊界

```text
OCR 提供者（Provider）   = 辨識與位置證據生產者（Recognition & Location Evidence）
AGY                     = 唯一語意權威（Semantic Authority & Claim Verification）
Phase 12 Grounding      = 凍結的接地契約與追溯驗證（Frozen Grounding System）
```

- **OCR 絕非語意權威**：OCR 提供者只產出字元辨識結果、邊界框（Bounding Boxes）與辨識信賴度，不具備判斷內容重要性、論點成立與否或事實真偽之權限。
- **禁止自動升級**：OCR 產出的文字區塊（OCR Blocks）**絕不可**自動升級為 Phase 12 語意來源單元（Semantic Source Units），必須經由 AGY 進行語意切分與審查。

---

## 2. 提供者解析與備援政策（Resolution & Fallback Policy）

### 2.1 確定性解析優先順序（Provider Resolution Precedence）

當文件或頁面需要進行 OCR 時，系統依以下順序確定性解析提供者（單次呼叫覆寫優先於持久化設定）：

1. **命令列／呼叫顯式提供者覆寫**（`--ocr-provider`）
2. **專案層級顯式設定**（`project.ocr.provider`）
3. **使用者／全域層級顯式設定**（`user.ocr.provider`）
4. **agy-ppt 預設本機提供者**（`tesseract`）
5. **若皆不可用 → 顯式拋出錯誤並終止**（`OCR_PROVIDER_UNAVAILABLE`）

### 2.2 嚴格禁止靜默備援（No Silent Fallback）

若使用者已顯式指定特定提供者（例如 `ocr.provider = "custom-cloud-ocr"`），但該提供者因網路異常、憑證無效或契約不符而失敗：

> [!CAUTION]
> **嚴禁靜默切換回預設本機提供者。**

```text
顯式指定提供者失敗 ──(預設: allow_fallback=false)──> 立即報錯 (FAIL)
```

靜默備援會破壞辨識品質的可預期性與可重現性，並可能在使用者預期使用高精度私有模型時，產出不符預期的辨識結果。

### 2.3 顯式備援宣告與歷程記錄（Explicit Fallback）

僅在使用者**顯式啟用備援**（例如設定 `ocr.allow_fallback = true`）時，系統方可在指定提供者失敗後轉向預設提供者。

此時系統**必須**在辨識歷程（Provenance）中完整記錄：
- `requested_provider`：原始請求之提供者（如 `enterprise-ocr`）
- `actual_provider`：實際執行之提供者（如 `tesseract`）
- `fallback_used`：`true`
- `fallback_reason`：明確失敗代碼（如 `OCR_PROVIDER_UNAVAILABLE`）

---

## 3. 預設本機引擎評估（Default Engine Evaluation）

agy-ppt 仍需內建開箱即用的預設本機 OCR 解決方案，作為無顯式設定使用者的可靠基底。

### 3.1 候選引擎評估矩陣

本評估明確區分「**目前觀察官方版本（Current Observed Version，截至 2026-09-06）**」與「**規劃支援版本範圍（Planned Supported Version Range）**」，嚴禁將動態的「最新版（latest）」作為重現性契約：

| 候選對象 | 目前觀察官方版本 (Current Observed) | 規劃支援版本範圍 (Planned Range) | 軟體授權 | 繁體中文 (zh-TW) | 英文 | 離線執行能力 | macOS (含 Apple Silicon) | Linux CI (Ubuntu) | 評估分類 (Classification) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Tesseract OCR** | 5.5.3 (官方發布) | v5.3+ – v5.5.x | Apache 2.0 | 支援 (`chi_tra` 需就緒並校驗指紋) | 支援 (`eng`) | 100% 離線 (本地 traineddata) | 完整支援 (`brew`)，原生 arm64 | 發行版套件可用 (`apt-get`)，無執行期權重下載 | **DEFAULT LOCAL PROVIDER**（選定） |
| **PaddleOCR (PP-OCR)** | v3.7.0 / PP-OCRv6 (官方發布) | PP-OCRv4 / PP-OCRv6 | Apache 2.0 | 優異 (`chinese_cht` / 統一多語言) | 支援 | 依賴模型權重，預設動態下載 | 安裝相依沉重，macOS arm64 相容性脆弱 | 相依 PaddlePaddle (1GB+)，CI 易超時/OOM | **OPTIONAL PROVIDER / ADAPTER** |
| **Apple Vision** | macOS 11+ 內建 (Vision framework) | macOS 11+ / 12+ | 專有 (Apple) | 優異 | 優異 | 100% 離線 (硬體加速) | 系統內建，免安裝額外二進位 | **完全無法在 Linux 執行** | **PLATFORM-SPECIFIC PROVIDER** |
| **OCRmyPDF** | 17.11.0 (PyPI 穩定版) | v16.x – v17.x | MPL-2.0 | 依賴後端 (Tesseract) | 依賴後端 | 本地工具鏈 | 需安裝完整 PDF 工具鏈 | CI 依賴 Ghostscript/qpdf/unpaper | **PDF WORKFLOW WRAPPER** |
| **EasyOCR** | 1.7.2 (PyPI 穩定版) | v1.7.x | Apache 2.0 | 支援 (`ch_tra`) | 支援 | 依賴 PyTorch 權重 | 相依 PyTorch (1.5GB+)，安裝耗時 | CI 下載 PyTorch 極重，記憶體消耗大 | **OPTIONAL PROVIDER / ADAPTER** |
| **RapidOCR** | 1.4.4 (`rapidocr-onnxruntime`) | v1.3.x – v1.4.x | Apache 2.0 | 支援 (ONNX 權重) | 支援 | 需管理 ONNX 模型檔 | 輕量 ONNX Runtime，跨平台良好 | 輕量，但繁體模型需額外管理與校驗 | **OPTIONAL PROVIDER / ADAPTER** |

### 3.2 預設引擎選定決策：Tesseract OCR (v5.x)

- **選定預設本機提供者**：**Tesseract OCR (v5.x)**
- **決策信心度**：**HIGH**
- **核心選定理由**：
  1. **發行版套件可用性與本機執行（無執行期模型下載）**：Tesseract 與所需語言包皆可透過主流作業系統發行版套件管理器取得（macOS `brew` 原生支援 Apple Silicon；Ubuntu Linux CI 透過 `apt-get` 安裝）。一旦安裝所需引擎與經釘選／校驗之語言資料，OCR 執行完全在本機進行，**不需於執行時期動態下載可變動的 OCR 模型（no runtime download of mutable OCR models）**，杜絕 Actions 超時與非預期模型漂移風險。
     - **繁體中文語言包特別要求**：繁體中文語言資料（如 `chi_tra` traineddata）必須在執行環境中就緒，其來源出處與雜湊指紋（provenance / digest）必須由未來實作完整擷取並記錄於 OCR 證據歷程中，絕不可假設任何環境皆預先具備該語言資料。
  2. **完全離線與無隱藏連線**：模型以靜態 `.traineddata` 檔案發行，可釘選特定版本 commit SHA 與 SHA-256 雜湊值進行確定性校驗，執行過程無任何遙測或動態聯網。
  3. **豐富的結構化定位資訊**：原生 TSV / hOCR 輸出具備完整邊界框座標（`left`, `top`, `width`, `height`）、階層結構（頁、區塊、段落、行、詞）與 0–100 的信心度指標。
  4. **雙語混合支援**：透過 `-l chi_tra+eng` 原生支援繁體中文與英文混合文件辨識。
  5. **寬鬆開源授權**：Apache 2.0 授權條款與本專案 MIT 授權完全相容。

### 3.3 其他候選者定位與分級

- **PaddleOCR**：辨識精度極佳，但運行庫沉重且預設下載行為不易受控，定位為未來 **Phase 15.4 的進階選用提供者（Optional Provider Adapter）**。
- **Apple Vision**：macOS 原生表現頂尖，但無法跨平台與 Linux CI 運行，定位為未來的 **平台專用外掛提供者（Platform-Specific Adapter）**。
- **OCRmyPDF**：本質是產出 Searchable PDF 的封裝工具，與 agy-ppt 提取結構化文字證據的需求不合，定位為 **非核心支援工具**。

---

## 4. 文件類型啟用與路由架構（Activation & Routing）

系統依來源文件特性進行確定性路由，**絕不**對所有 PDF 盲目執行耗時且可能失真的 OCR：

```text
來源文件
   │
   ├── 純數位 PDF（具完整文字層）
   │        ↓
   │     Phase 13 確定性文字擷取（pypdf，無 OCR）
   │
   ├── 純影像 / 掃描 PDF（無文字層或文字損壞）
   │        ↓
   │     確定性頁面光柵化（Rasterization） → OCR 提供者
   │
   ├── 混合型 PDF（部分頁面具文字，部分為掃描圖）
   │        ↓
   │     頁層級路由（Page-Level Routing）：
   │       - 具文字頁面 → Phase 13 原生擷取
   │       - 純影像頁面 → 光柵化 + OCR 提供者
   │
   ├── 已具備文字層之 Searchable / OCR PDF
   │        ↓
   │     保守預設：優先使用既有文字層；
   │     僅在使用者顯式宣告 force_ocr=true 時重新執行 OCR
   │
   └── 獨立圖片（PNG, JPEG, TIFF）
            ↓
         影像驗證與預處理 → OCR 提供者（使用影像原生 locator）
```

---

## 5. 來源身分與確定性緩存（Identity & Provenance）

### 5.1 來源指紋唯一權威（Source Digest Authority）

所有 OCR 來源指紋維持全專案唯一權威：

```text
source_digest = SHA-256(原始來源位元組 raw source bytes)
```

光柵化後之頁面影像、中間臨時檔案或萃取文字的雜湊值**不可**取代 `source_digest`。

### 5.2 確定性 OCR 成果識別與失效機制（Stale Detection）

OCR 結果之唯一識別與重用性由以下維度確定性決定：
- `source_digest`
- 頁碼／影像 locator
- 提供者身分與版本（`provider_id`, `provider_version`）
- 引擎與模型版本／指紋（`engine_version`, `model_digest`）
- 語言與呼叫設定（`language_config`, `ocr_parameters`）
- 光柵化設定（`raster_dpi`, `raster_renderer_version`）

任何一項變更皆視為**證據過期（Stale Evidence）**，必須重新執行辨識，確保結果的可追溯性與可驗證性。

---

## 6. 高風險數值與符號防護（High-Risk OCR QA）

OCR 辨識常見字形混淆（如 `0`/`O`、`1`/`I`/`l`、`5`/`S`、`8`/`B`、小數點遺漏、負號丟失、百分比與貨幣符號扭曲）。

- **禁止抽取層靜默修正**：OCR 抽取階段**絕不**可擅自將文字修改（例如將 `O` 猜測為 `0`），更不可透過大型語言模型進行未具說明的「自動潤稿」。
- **保留原始辨識與正規化分離**：原始文字（`raw_text`）與基礎 Unicode 正規化文字（`normalized_text`）並存記錄。
- **語意層警示提示**：於 OCR 證據物件中標記數值與敏感符號區塊，供 AGY 語意審查時作為高風險關注訊號。

---

## 7. 隱私與遠端提供者邊界（Privacy Boundary）

- **預設本機提供者零外洩保證**：預設的 Tesseract 5 完全在本地 process 執行，宣告 `source_may_leave_local_machine = false`。
- **自備遠端提供者顯式揭露**：若使用者自備並配置雲端或遠端 OCR 服務（如 Cloud Vision），提供者契約中必須明確宣告：
  ```json
  "execution_location": "remote",
  "source_may_leave_local_machine": true
  ```
- 系統啟動時若偵測到遠端提供者，必須顯式告知操作人員來源內容將傳輸至本機之外，杜絕靜默外傳。

---

## 8. Phase 15 工程實作路線圖（Roadmap）

Phase 15 分為七個嚴謹推進的子階段：

```text
Phase 15.0 (Current)
OCR 提供者架構、BYO-OCR 契約與預設引擎評估決策 (AGY 主導架構/文件)
   │
Phase 15.1
OCR 提供者契約核心規格與預設本機提供者基礎建設 (Kiro 實作)
   │
Phase 15.2
掃描與純影像 PDF OCR 支援 (光柵化與頁層級路由)
   │
Phase 15.3
獨立圖片格式 (PNG, JPEG) OCR 支援與圖片原生 Locator
   │
Phase 15.4
自備 OCR (BYO-OCR) 與外部自訂提供者動態註冊整合
   │
Phase 15.5
OCR 證據 → AGY 語意層 → Phase 12 來源接地整合
   │
Phase 15.6
真實公開來源驗證、確定性門檻測試與生產發布就緒
```

### 未來階段就緒狀態（Future Phase Readiness Status）

- **Phase 15.1**: HANDOFF READY WHEN KIRO IS AVAILABLE
- **Phase 15.2**: ARCHITECTURALLY SPECIFIED / DEPENDS ON 15.1
- **Phase 15.3**: ARCHITECTURALLY SPECIFIED / DEPENDS ON 15.1
- **Phase 15.4**: ARCHITECTURALLY SPECIFIED / DEPENDS ON 15.1
- **Phase 15.5**: ARCHITECTURALLY SPECIFIED / DEPENDS ON 15.1–15.4
- **Phase 15.6**: ARCHITECTURALLY SPECIFIED / DEPENDS ON PRIOR PHASES

### 未來 Phase 15.1 範圍預備（Kiro-Ready Scope）
- 定義 `OCRProvider` 抽象基底介面與 `OCRProviderCapabilities` 結構。
- 實作預設 `TesseractOCRProvider` 本機適配器。
- 實作契約校驗器與 `OCR_PROVIDER_*` 錯誤分類系統。
- 建立確定性假提供者（Synthetic Mock Provider）用於輕量 CI 驗證。
