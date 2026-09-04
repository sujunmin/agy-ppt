# Source Ingestion & Locator Extraction（Phase 13.1 + 13.2）

本文件描述 Phase 13 建立的 deterministic source ingestion 系統：把一份**本機**來源
檔案轉成正規化的 extraction blocks 與 source-format-native locators，作為 Phase 12
grounding 系統的上游生產者。

## 1. 位置與邊界

```text
local source
  → format detection
  → deterministic extractor
  → normalized extracted blocks + locators   ← Phase 13
  → AGY semantic segmentation
  → Phase 12 source_inventory.json
  → Phase 12 grounding workflow
```

最重要的邊界：

```text
extraction ≠ semantic understanding
```

Phase 13 只決定文件**機械上**含有什麼：某段文字在第幾頁、被哪個 Markdown heading
包住、佔哪一段行號。它**不**決定什麼重要、什麼是 HIGH priority、claim 是什麼意思、
來源是否支持某個 claim、哪些內容該進投影片，也不做 semantic segmentation。

這些全部仍屬 AGY。因此：

```text
Phase 13 extracted block  ≠  Phase 12 semantic source unit
```

Phase 13 不會把任何 block 自動升級成 source unit；ingestion 也不會寫出任何 Phase 12
artifact。

## 2. 模組與 CLI

| 檔案 | 角色 |
| --- | --- |
| `skills/agy-ppt/scripts/source_ingestion.py` | 核心模組，唯一的 extraction 實作 |
| `skills/agy-ppt/scripts/ingest_source.py` | 薄 CLI adapter，完全委派給核心模組 |

Extraction 邏輯刻意不放進 `source_grounding.py`：Phase 13 是 extraction，Phase 12 是
grounding，兩者是不同關注點。

主要 Python API：

```python
from source_ingestion import ingest_source

result = ingest_source("/path/to/report.pdf", "src_report")
```

CLI：

```bash
python3 skills/agy-ppt/scripts/ingest_source.py \
    --source /path/to/report.pdf \
    --source-id src_report \
    --output /path/to/workspace/extraction.json
```

成功時輸出 `source_id`、`source_format`、`source_digest`、`extractor_version`、
`block_count` 與 output 路徑；失敗時以非零 exit code 與穩定 error code 回報，不會為
一般的 unsupported-source 錯誤印出 stack trace。

`--detect-only` 只回報偵測到的格式。

## 3. 支援與不支援的格式

| 格式 | 狀態 |
| --- | --- |
| PDF（具可擷取文字層） | 支援 |
| Markdown | 支援 |
| Plain text | 支援 |
| DOCX | 尚未支援 |
| HTML | 尚未支援 |
| OCR / 掃描影像 PDF | 不支援 |
| PowerPoint / 試算表 | 不支援 |
| 遠端 URL / 網頁抓取 | 不支援 |

Phase 13.2 只處理**本機檔案**。來源取得（下載、認證、網路）屬 orchestration 層行為，
不在本模組內。

### PDF 需要可擷取文字層

PDF 支援**不是**萬用 PDF 解析。掃描或純影像 PDF 會以
`SOURCE_TEXT_UNAVAILABLE` 明確失敗，而不是回傳「成功但沒有文字」。

Phase 13.2 明確禁止任何 OCR fallback：不使用 Tesseract、雲端 OCR、vision API、
Codex OCR 或任何 image-to-text API。沒有隱形 fallback。

## 4. Format detection

`detect_source_format(path)` 是唯一的格式判定 authority，判定順序：

1. 檔案開頭為 `%PDF-` signature → `pdf`（signature 優先於副檔名，所以標錯副檔名或
   沒有副檔名的 PDF 仍會被正確路由）。
2. 否則依副檔名判定 `markdown`（`.md`/`.markdown`/`.mdown`）或 `text`
   （`.txt`/`.text`）——純文字檔沒有 signature 可驗。
3. 其餘皆為 `unsupported`，包含只是**取名**為 `.pdf` 但沒有 PDF signature 的檔案。

## 5. Locator 語意

所有編號皆為 **1-based**。

Phase 13 locator 直接採用 frozen Phase 12 的 locator kinds，因此 handoff 不需要任何
轉換，也不需要修改 Phase 12。

### PDF

```json
{ "kind": "page", "start": 3, "end": 3 }
```

Granularity 刻意停在 page 層級：這是 PDF 能可靠揭露、又不需要猜測版面的唯一切分。
輸出的頁碼是讀者看到的 1-based 頁碼，絕不外露 parser 內部的 0-based index。

### Markdown

```json
{
  "kind": "section",
  "label": "Architecture > Source Grounding",
  "heading_path": ["Architecture", "Source Grounding"],
  "start_line": 42,
  "end_line": 67
}
```

Section 從 heading 行延伸到下一個任意層級 heading 的前一行。支援 H1–H6。

同名 heading 不會互相碰撞：`heading_path` 記錄完整層級，行號範圍也不同，因此
`block_id` 必然不同。

Fenced code block（```` ``` ```` 或 `~~~`）內看起來像 heading 的行**不會**產生 section。

### Plain text

```json
{ "kind": "line_range", "start": 10, "end": 16 }
```

以空行切分 paragraph，純機械切法，不做 semantic chunking、不做句子切分、不做主題偵測。

## 6. Block 契約

```text
block_id
block_type      page | markdown_section | paragraph
text
locator
ordinal
metadata
```

Extraction result：

```text
schema_version
extractor_version
source_id
source_format
source_digest
blocks[]
```

## 7. 穩定 block_id 與 determinism

`block_id` 形如 `blk:<source_id>:<hex12>`，由下列輸入 deterministic 推導：

```text
sha256(source_id + "\n" + canonical_locator_json + "\n" + ordinal)[:12]
```

它**不**依賴：絕對檔案路徑、暫存目錄、process id、timestamp，或單純的隨機 UUID。

因此在相同 source bytes、相同 extractor version、相同 extraction rules 之下重複
ingest，必然得到：

```text
相同 block IDs
相同 locator values
相同 block 順序
```

Block 順序由 `ordinal` 明確決定（PDF 依頁碼、Markdown 依 outline 出現順序、
plain text 依行號），不依賴 filesystem 列舉順序或 mapping 走訪順序。

### Absolute path independence

同樣內容放在不同目錄 ingest，會產生完全相同的結果。logical source identity 由
`source_id` 決定，不由檔案位置決定；Phase 12 handoff 的公開 metadata 不含任何本機
絕對路徑。

## 8. Source digest

Phase 13 直接委派 Phase 12 的 `compute_source_digest()`，**不**另外定義第二套
fingerprint 語意。全專案只有一個 canonical source fingerprint 定義。

Digest 一律計算在**原始 bytes** 上，不做前置正規化，因此與 Phase 12 記錄的值一致。

## 9. Newline 與 encoding

| 項目 | 行為 |
| --- | --- |
| `source_digest` | 原始 bytes，未正規化 |
| extracted text | CRLF 與單獨 CR 正規化為 LF |
| Markdown/TXT encoding | UTF-8 與 UTF-8 with BOM（BOM 會被去除） |
| 不支援的 encoding | `SOURCE_ENCODING_UNSUPPORTED`，不產生亂碼 |

因此同一份內容以 LF 與 CRLF 儲存時，extracted blocks 完全相同，但 `source_digest`
不同——因為 bytes 確實不同。這是刻意的：digest 描述位元組，blocks 描述內容。

## 10. Extractor version

```text
extractor_version = "1"
```

刻意與 release version 及 Git tag 無關。若未來 extraction 行為改變，已持久化的結果
仍可被識別。不使用 `v0.2.0` 這類值。

## 11. Error taxonomy

| Error code | 意義 |
| --- | --- |
| `SOURCE_FORMAT_UNSUPPORTED` | 格式不在 Phase 13.2 支援範圍 |
| `SOURCE_FILE_NOT_FOUND` | 本機檔案不存在 |
| `SOURCE_READ_FAILED` | 檔案無法讀取／輸出無法寫入 |
| `SOURCE_ENCODING_UNSUPPORTED` | 非 UTF-8（含 BOM）文字檔 |
| `SOURCE_TEXT_UNAVAILABLE` | 結構有效但沒有可擷取文字（掃描 PDF、空白文件） |
| `SOURCE_EXTRACTION_FAILED` | 文件結構損毀或擷取過程失敗 |

這組 code 與 Phase 12 grounding code、image-worker code 刻意不重疊：ingestion 問題
絕不會被記錄成 traceability、coverage 或 image-generation 失敗。

`SOURCE_TEXT_UNAVAILABLE` 與 `SOURCE_EXTRACTION_FAILED` 也刻意分開：結構損毀的 PDF
不會被誤報為「有效但無文字」。

## 12. Phase 12 handoff

正確邊界：

```text
Phase 13 extracted blocks
  → AGY review / semantic segmentation
  → Phase 12 source inventory units
```

`phase12_locator(block)` 回傳可直接交給 `SourceInventory.add_unit()` 的 locator。
是否要把某個 block 升級成 source unit、給它什麼 `unit_type`、什麼 `priority`、
什麼 `title`，全部是 AGY 的決定。

Phase 12 是 **COMPLETE / FROZEN**：Phase 13 沒有、也不需要修改 Phase 12 的任何契約
或語意。

## 13. 隱私

- 只讀取本機檔案，不發出任何網路請求。
- 不記錄、不複製、不轉傳任何 credential 或 OAuth session 資料。
- Extraction result 不含本機絕對路徑。
- 測試 fixture 全為合成資料：不使用真實客戶文件、私人來源，也不會把第三方受著作權
  文件放進 repository 只為了測試。

## 14. 已知限制

- 尚未支援 DOCX ingestion。
- 尚未支援 HTML ingestion。
- 不支援 OCR；掃描或純影像 PDF 會明確失敗。
- PDF 需要可擷取文字層。
- PDF granularity 目前為 page 層級，不做版面語意重建。
- Plain text 只做空行切分，不做 semantic chunking。
- Extraction 不等於 semantic segmentation；AGY 仍是 semantic authority。
