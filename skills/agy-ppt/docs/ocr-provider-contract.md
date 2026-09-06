# OCR Provider Contract Specification

本文件是 `agy-ppt` OCR 提供者契約（OCR Provider Contract）之規範性技術標準（Normative Specification）。所有 OCR 提供者（包含預設本機提供者與使用者自備之 BYO-OCR 提供者）皆必須遵循此契約，將辨識結果標準化為統一的 OCR 證據模型。

---

## 1. 提供者能力分級（Capability Tiers）

契約將能力劃分為三級：

| 能力分級 | 定義 | 缺漏時之行為 |
| --- | --- | --- |
| **REQUIRED（必要）** | 提供者身分、基礎辨識文字、來源相對 locator、執行位置宣告 | **直接拒絕提供者**（`OCR_PROVIDER_CONTRACT_INVALID` 或 `OCR_PROVIDER_CAPABILITY_MISSING`） |
| **RECOMMENDED（建議）** | 邊界框（Bounding boxes）、信賴度指標、語言資訊、模型指紋 | **接受提供者**，但記錄降級警示（Warning / reduced capability） |
| **OPTIONAL（選用）** | 單詞級邊界框、表格結構、版面區域重建、文字方向偵測 | **接受提供者**，系統自動略過未支援項目 |

---

## 2. 提供者能力宣告物件（OCRProviderCapabilities）

提供者必須實作能力宣告介面，回傳符合以下結構之能力物件：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "OCRProviderCapabilities",
  "type": "object",
  "required": ["text", "locators", "execution_location", "source_may_leave_local_machine"],
  "properties": {
    "text": {
      "type": "boolean",
      "description": "是否能產出文字辨識結果 (必須為 true)"
    },
    "locators": {
      "type": "boolean",
      "description": "是否能產出符合來源之 1-based locator (必須為 true)"
    },
    "execution_location": {
      "type": "string",
      "enum": ["local", "remote"],
      "description": "執行環境位置：local 為本機處理，remote 為雲端或遠端服務"
    },
    "source_may_leave_local_machine": {
      "type": "boolean",
      "description": "來源資料是否可能傳輸至本機之外"
    },
    "bounding_boxes": {
      "type": "boolean",
      "default": false,
      "description": "是否提供文字區塊或行之邊界框"
    },
    "word_boxes": {
      "type": "boolean",
      "default": false,
      "description": "是否提供單詞層級之邊界框"
    },
    "confidence": {
      "type": "boolean",
      "default": false,
      "description": "是否提供辨識信賴度數值"
    },
    "orientation": {
      "type": "boolean",
      "default": false,
      "description": "是否具備頁面或文字旋轉角度判定能力"
    },
    "tables": {
      "type": "boolean",
      "default": false,
      "description": "是否能辨識結構化表格"
    },
    "layout_regions": {
      "type": "boolean",
      "default": false,
      "description": "是否提供多欄版面區域劃分"
    }
  }
}
```

---

## 3. 定位器契約（Locator Contract）

所有 OCR 證據必須與原始來源綁定精確的定位器，嚴格維持 **1-based** 索引：

### 3.1 多頁文件（PDF）
- 使用 Phase 12 標準的 `page` locator kind：
  ```json
  {
    "kind": "page",
    "page": 1,
    "total_pages": 42
  }
  ```
- **絕無 0-based 偏誤**：第 1 頁之頁碼必須為 `1`。

### 3.2 獨立圖片（PNG, JPEG, TIFF）
- 使用影像專屬 locator，**絕不**虛構 PDF 頁碼：
  ```json
  {
    "kind": "image",
    "ordinal": 1
  }
  ```

---

## 4. 座標系統與邊界框規範（Bounding Box Contract）

當提供者支援邊界框時，座標必須正規化至統一的相對比例系統：

- **原點**：影像左上角（Top-Left）為 `(0.0, 0.0)`。
- **軸向**：X 軸水平向右遞增，Y 軸垂直向下遞增。
- **數值範圍**：浮點數 `[0.0, 1.0]`，代表相對該頁面／影像寬高之百分比：
  - `x`: 左邊界相對寬度
  - `y`: 上邊界相對高度
  - `width`: 區塊寬度相對總寬度
  - `height`: 區塊高度相對總高度
- **原始像素輔助資訊**（選用）：可於 `pixel_dimensions` 紀錄原始像素座標以供審查。

---

## 5. 辨識信賴度契約（Confidence Semantics）

各 OCR 引擎（如 Tesseract 0–100、Apple Vision 0.0–1.0、Cloud Vision 百分比）之評分模型不具直接等價性。本契約禁止擅自對齊或捏造統一信賴度，而是保留提供者原生語意：

```json
{
  "raw_confidence": 89.5,
  "confidence_scale": "0-100",
  "confidence_source": "tesseract_word_average"
}
```

AGY 根據提供者宣告之尺標進行適應性解讀，而非假設所有 0.9 皆代表相同信心。

---

## 6. 標準化 OCR 證據模型（Canonical OCR Evidence Schema）

提供者執行完成後，必須回傳或經適配器轉換為以下標準結構：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "OCREvidence",
  "type": "object",
  "required": [
    "source_id",
    "source_digest",
    "provider",
    "provenance",
    "pages"
  ],
  "properties": {
    "source_id": { "type": "string" },
    "source_digest": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
    "provider": {
      "type": "object",
      "required": ["provider_id", "provider_version", "engine_name"],
      "properties": {
        "provider_id": { "type": "string" },
        "provider_version": { "type": "string" },
        "engine_name": { "type": "string" },
        "engine_version": { "type": "string" },
        "model_id": { "type": "string" },
        "model_digest": { "type": "string" }
      }
    },
    "provenance": {
      "type": "object",
      "required": ["execution_location", "source_may_leave_local_machine", "fallback_used"],
      "properties": {
        "execution_location": { "type": "string", "enum": ["local", "remote"] },
        "source_may_leave_local_machine": { "type": "boolean" },
        "requested_provider": { "type": "string" },
        "actual_provider": { "type": "string" },
        "fallback_used": { "type": "boolean" },
        "fallback_reason": { "type": "string" },
        "raster_dpi": { "type": "integer" },
        "raster_renderer": { "type": "string" }
      }
    },
    "pages": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["locator", "raw_text", "normalized_text", "blocks"],
        "properties": {
          "locator": { "type": "object" },
          "raw_text": { "type": "string" },
          "normalized_text": { "type": "string" },
          "high_risk_signals": {
            "type": "array",
            "items": { "type": "string" },
            "description": "標記包含數字、貨幣、日期或混淆字元之可疑區塊"
          },
          "blocks": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["block_id", "text", "bounding_box"],
              "properties": {
                "block_id": { "type": "string" },
                "text": { "type": "string" },
                "bounding_box": { "type": "object" },
                "confidence": { "type": "object" }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## 7. 錯誤分類體系（Error Taxonomy）

OCR 提供者契約定義獨立且穩定的錯誤代碼，與 Phase 12 接地及 Phase 13 擷取錯誤完全不重疊：

| 代碼 | 嚴重性 | 說明 |
| --- | --- | --- |
| `OCR_PROVIDER_NOT_FOUND` | 致命 | 找不到使用者指定之提供者識別碼 |
| `OCR_PROVIDER_UNAVAILABLE` | 致命 | 提供者二進位檔或遠端端點暫時無法存取 |
| `OCR_PROVIDER_CONTRACT_INVALID` | 致命 | 提供者回傳之資料違反必要契約結構 |
| `OCR_PROVIDER_CAPABILITY_MISSING` | 致命 | 提供者缺少必要的契約功能（如缺少文字或定位器） |
| `OCR_PROVIDER_VERSION_UNAVAILABLE` | 警告/錯誤 | 無法偵測提供者或底層引擎版本 |
| `OCR_PROVIDER_OUTPUT_INVALID` | 致命 | 萃取結果 JSON 格式損毀或欄位型態錯誤 |
| `OCR_PROVIDER_FAILED` | 致命 | 引擎內部執行程序崩潰或傳回非零結束代碼 |
| `OCR_LANGUAGE_UNSUPPORTED` | 致命 | 提供者不支援請求的語系模型（如缺乏繁體中文模型） |
| `OCR_MODEL_UNAVAILABLE` | 致命 | 找不到本機模型權重或 traineddata 檔案 |
| `OCR_EXTRACTION_FAILED` | 致命 | 影像損毀導致光學字元辨識處理程序失敗 |
| `OCR_TEXT_UNAVAILABLE` | 警告 | 頁面或影像經 OCR 處理後未偵測到任何文字字元 |
| `OCR_RASTERIZATION_FAILED` | 致命 | PDF 頁面轉換為光柵化影像階段失敗 |
| `OCR_FALLBACK_NOT_ALLOWED` | 致命 | 指定提供者失敗，且使用者未顯式允許備援 |
| `OCR_SOURCE_CHANGED` | 狀態 | 原始來源位元組 SHA-256 變更，先前 OCR 快取失效 |
| `OCR_PROVIDER_CHANGED` | 狀態 | 提供者身分變更，需重新執行辨識 |
| `OCR_CONFIG_CHANGED` | 狀態 | OCR 語言、DPI 或光柵化設定變更，緩存證據過期 |
