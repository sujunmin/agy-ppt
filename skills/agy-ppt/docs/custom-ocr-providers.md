# 自訂 OCR 提供者整合指南（Custom OCR Providers Guide）

本文件提供開發者與企業使用者在 `agy-ppt` 中整合「自備 OCR 提供者（Bring Your Own OCR, BYO-OCR）」的實務指南。

> [!NOTE]
> 本文件為 **Phase 15.0 架構與契約規範文件**。此處展示之類別介面與設定語法為**概念性設計（Conceptual Specification）**，實際執行層將於後續階段（Phase 15.1+）陸續落地。

---

## 1. 核心整合原則

`agy-ppt` 採用開放且標準化的提供者架構（Provider Architecture）。使用者與企業可依需求整合專有的 OCR 引擎、雲端辨識服務（如 Google Cloud Vision、Azure AI Document Intelligence、AWS Textract）或自研深度學習模型。

所有自訂 OCR 提供者皆必須遵守 [OCR Provider Contract Specification](ocr-provider-contract.md) 中定義的統一輸出規格與行為契約。

### 嚴格合規保證（Rejection Rule）

> [!IMPORTANT]
> **若您所整合的 OCR 產品或適配器未能滿足「必要契約（Required Contract）」，`agy-ppt` 將直接拒絕載入或執行該提供者，並中止辨識流程。**

---

## 2. 能力分級與缺漏處理原則

`agy-ppt` 將 OCR 功能劃分為三個層級。實作自訂提供者時請注意不同層級缺漏時的系統行為：

| 能力層級 | 包含項目 | 缺漏時之行為 |
| --- | --- | --- |
| **REQUIRED（必要）** | 提供者身分識別（`provider_id`、`provider_version`）、基礎純文字萃取（`raw_text`）、來源相對定位器（1-based `locator`）、執行環境位置宣告（`execution_location`）、隱私資料外流宣告（`source_may_leave_local_machine`） | **直接拒絕（REJECT）**。<br>拋出 `OCR_PROVIDER_CONTRACT_INVALID` 或 `OCR_PROVIDER_CAPABILITY_MISSING`，終止作業。 |
| **RECOMMENDED（建議）** | 文字區塊邊界框（`bounding_boxes`，0.0–1.0 正規化座標）、辨識信賴度指標（`confidence`）、語言偵測資訊（`language`）、底層引擎/模型版本（`engine_version`、`model_digest`） | **接受但降級（ACCEPT + WARNING）**。<br>記錄警示並繼續執行，但下游無法進行幾何校正與低信心警示。 |
| **OPTIONAL（選用）** | 單詞級細部邊界框（`word_boxes`）、結構化表格辨識（`tables`）、多欄版面區域重建（`layout_regions`）、旋轉角度偵測（`orientation`） | **完全接受（ACCEPT）**。<br>正常執行，系統自動略過未支援的版面增強功能。 |

---

## 3. 提供者概念適配器結構（Conceptual Adapter Patterns）

自訂提供者通常透過「適配器（Adapter）」將原生 OCR 工具的輸出轉換為 `agy-ppt` 標準的 [`OCREvidence`](ocr-provider-contract.md#6-標準化-ocr-證據模型canonical-ocr-evidence-schema) 結構。

### 模式 A：Python 內部類別適配器（In-Process Adapter）

實作 `BaseOCRProvider` 概念抽象介面：

```python
# 概念設計：預期於 Phase 15.1+ 實現的抽象基礎介面
from typing import Dict, Any, List

class CustomOCRProvider:
    """自訂本機或內嵌 OCR 提供者適配器範例"""

    @property
    def provider_id(self) -> str:
        return "custom-paddle-ocr"

    @property
    def provider_version(self) -> str:
        return "1.0.0"

    def get_capabilities(self) -> Dict[str, Any]:
        """宣告能力物件（必須滿足 Required 欄位）"""
        return {
            "text": True,                               # REQUIRED
            "locators": True,                           # REQUIRED
            "execution_location": "local",              # REQUIRED: 'local' 或 'remote'
            "source_may_leave_local_machine": False,    # REQUIRED
            "bounding_boxes": True,                     # RECOMMENDED
            "confidence": True,                         # RECOMMENDED
            "tables": False,                            # OPTIONAL
        }

    def extract(self, source_path: str, pages: List[int], options: Dict[str, Any]) -> Dict[str, Any]:
        """
        執行文字辨識並轉換為標準 OCREvidence 格式
        :param source_path: 輸入影像或光柵化後頁面影像路徑
        :param pages: 目標頁碼清單 (1-based)
        :param options: 執行參數 (如語言代碼)
        :return: 符合 OCREvidence Schema 之字典
        """
        # 1. 呼叫底層模型辨識
        # 2. 座標正規化為 [0.0, 1.0]
        # 3. 封裝標準 pages 與 blocks
        # 4. 回傳包含 provider 與 provenance 之結構
        ...
```

### 模式 B：外部命令列包裝器（CLI Wrapper Adapter）

若您的 OCR 引擎為獨立二進位檔或指令碼（如專有 OCR 工具鏈），可實作 CLI 轉接器：

```bash
# 提供者呼叫格式概念規範
my-ocr-tool --input /tmp/page_1.png --output /tmp/ocr_raw.json --lang chi_tra
```

適配器工作流程：
1. 將 PDF 頁面光柵化為暫存影像。
2. 呼叫 CLI 程式並傳遞參數。
3. 讀取並驗證其結束代碼（Exit Code）。非 0 代碼拋出 `OCR_PROVIDER_FAILED`。
4. 解析輸出 JSON，將座標與文字組裝為 `OCREvidence` 格式。
5. 刪除暫存影像檔案。

### 模式 C：遠端 / 雲端 HTTP 端點適配器（Remote / Cloud API Adapter）

若整合企業內部專有 OCR 微服務或公共雲端 OCR API：

```json
POST https://ocr-gateway.enterprise.internal/v1/recognize
Content-Type: application/json
Authorization: Bearer <TOKEN>
```

遠端適配器必須遵守：
1. **明確隱私宣告**：宣告 `execution_location: "remote"` 與 `source_may_leave_local_machine: true`。
2. **憑證管理**：憑證與 Token 必須來自環境變數或專案密鑰管理工具，**嚴禁**將憑證寫入本機原始檔或儲存於公開 Repository。
3. **錯誤轉換**：網路超時或 HTTP 5xx 應明確對應至 `OCR_PROVIDER_UNAVAILABLE`；驗證授權失敗應對應至 `OCR_PROVIDER_FAILED`。

---

## 4. 隱私與資料安全邊界（Privacy & Data Boundaries）

自訂提供者牽涉資料處理位置時，必須誠實揭露隱私特徵：

- **本機執行（Local Execution）**：
  - `execution_location: "local"`
  - `source_may_leave_local_machine: false`
  - 原始影像與辨識文字僅於本機記憶體與指定之暫存目錄處理，不連外。
- **遠端或雲端執行（Remote Execution）**：
  - `execution_location: "remote"`
  - `source_may_leave_local_machine: true`
  - 使用者必須在專案設定中明確理解並授權資料上傳至第三方伺服器。
  - `agy-ppt` 不會將使用者機敏憑證（API Keys）持久化於接地快取中。

---

## 5. 提供者解析與備援政策實務（Resolution & Fallback Policy）

### 5.1 提供者解析優先順序（Provider Resolution Precedence）

系統依以下優先順序確定性解析應使用的 OCR 提供者（命令列單次呼叫覆寫優先於持久化設定）：

1. **命令列／呼叫顯式提供者覆寫**（例如 `--ocr-provider custom-ocr`）
2. **專案層級顯式設定**（`project.ocr.provider`，如 `agy-ppt.toml`）
3. **使用者／全域層級顯式設定**（`user.ocr.provider`）
4. **agy-ppt 預設本機提供者**（`tesseract`）
5. **若皆不可用 → 顯式拋出錯誤並終止**（`OCR_PROVIDER_UNAVAILABLE`）

### 5.2 嚴格禁止靜默備援（No Silent Fallback）

若您在專案中指定了自訂提供者（例如 `custom-ocr`）：

```toml
# 概念專案設定 (agy-ppt.toml)
[ocr]
provider = "custom-ocr"
allow_fallback = false # 預設值為 false
```

若 `custom-ocr` 發生錯誤（如服務斷線或程式當機），系統會**立即終止並拋出明確錯誤**，而**絕不**在未告知的情況下默默切換回 Tesseract。這確保了辨識品質與重現性符合您的預期。

### 5.3 顯式允許備援（Explicit Fallback）

僅在您明確設定 `allow_fallback = true` 時，系統才允許在自訂提供者失敗時切換至預設提供者：

```toml
[ocr]
provider = "custom-ocr"
allow_fallback = true
```

發生備援時，產出的 `OCREvidence` 中將忠實記載歷程資訊，供後續稽核：

```json
{
  "provenance": {
    "requested_provider": "custom-ocr",
    "actual_provider": "tesseract",
    "fallback_used": true,
    "fallback_reason": "OCR_PROVIDER_UNAVAILABLE: connection refused"
  }
}
```

---

## 6. 提供者合規自我檢查清單（Compliance Checklist）

在將自訂提供者交付正式環境前，請確認滿足以下項目：

- [ ] **提供者身分**：正確回傳不可為空的 `provider_id` 與 `provider_version`。
- [ ] **能力宣告完整**：回傳之能力字典包含必要之 `text`、`locators`、`execution_location`、`source_may_leave_local_machine` 四大布林/列舉值。
- [ ] **1-based 頁碼定位**：多頁文件之 `locator.page` 自 `1` 起算，絕無 0-based 偏誤；單一圖片使用 `locator.kind = "image"`。
- [ ] **邊界框標準化**：邊界框（若宣告支援）均正規化至 `[0.0, 1.0]` 浮點數，原點在左上角。
- [ ] **保留原始文字**：`raw_text` 保留引擎原生輸出（含換行符號），不擅自對文字進行「語意補全」或「自動修補」。
- [ ] **高風險訊號偵測**：針對數字、貨幣、日期、小數點區塊主動標記 `high_risk_signals`。
- [ ] **離線驗證支援**：若為本機提供者，在無網際網路環境下亦能完成驗證與萃取。
- [ ] **標準錯誤傳遞**：若發生異常，拋出或回傳契約所列之標準錯誤代碼（見第 7 節）。

---

## 7. 常見整合錯誤與診斷（Common Errors & Troubleshooting）

| 錯誤代碼 | 常見成因 | 解決方針 |
| --- | --- | --- |
| `OCR_PROVIDER_NOT_FOUND` | 指定的 `provider_id` 未註冊或拼寫錯誤 | 檢查命令列參數或設定檔中的提供者名稱是否與註冊名稱一致。 |
| `OCR_PROVIDER_UNAVAILABLE` | 二進位執行檔不存在、未加入 PATH，或遠端 API 無法連線 | 確認工具已正確安裝或 API 端點可正常存取。 |
| `OCR_PROVIDER_CONTRACT_INVALID` | 適配器回傳之 JSON 不符合 OCREvidence 規範（如缺漏必要欄位） | 依據 [OCR Provider Contract](ocr-provider-contract.md) 校驗輸出欄位型態。 |
| `OCR_PROVIDER_CAPABILITY_MISSING` | 提供者宣告缺少文字萃取或定位能力 | 確認 `get_capabilities()` 中 `text` 與 `locators` 皆為 `true`。 |
| `OCR_PROVIDER_FAILED` | 提供者內部例外崩潰或回傳非零結束代碼 | 檢查輸入影像格式是否受支援，或檢查引擎內部錯誤日誌。 |
| `OCR_LANGUAGE_UNSUPPORTED` | 請求的辨識語系（如 `chi_tra`）未安裝模型權重 | 下載或安裝該引擎對應的語言模型檔案（如 traineddata）。 |
| `OCR_FALLBACK_NOT_ALLOWED` | 自訂提供者執行失敗，且未啟用 `allow_fallback` | 修復自訂提供者問題，或於設定中顯式開啟 `allow_fallback = true`。 |
