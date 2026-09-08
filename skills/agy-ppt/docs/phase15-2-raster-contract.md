# Phase 15.2 PDF 光柵化與路由契約

本文件是文件／治理契約，不是功能發布。基線為 `074625912bf1451fe6a60cf99cd55f4365410b28`。Phase 15.1 為 **COMPLETE / MERGED / BASELINE FROZEN**；Phase 15.2 為 **NOT STARTED**。OCR JSON schemas 維持 **DEFERRED**。AGY 保有唯一語意權威。

本契約補充 [Phase 15 架構](phase15-ocr-architecture.md)、沿用 [Phase 15.1 provider contract](ocr-provider-contract.md)，不改寫既有 provider 行為。

## 1. 所有權與 additive 邊界

Phase 15.2 擁有 scanned/image-only PDF、逐頁 searchable/scanned 分類、確定性 PDF 頁面光柵化、逐頁 OCRProvider 呼叫、OCR-native PDF page locator、有序逐頁 OCR evidence、mixed-PDF 路由與明確失敗行為。

排除 Phase 15.3 公開 standalone image ingestion、Phase 15.4 完整 custom-provider registration UX、Phase 15.5 OCR → AGY／Phase 12 grounding，以及 Phase 15.6 真實來源 production validation。

實作 MUST additive：不得要求修改 Phase 12 source digest／locator validation、Phase 13 ExtractionResult 或 frozen Phase 13 source ingestion production behavior。若實作需要此類變更，停止並回報 `PHASE_15_2_FROZEN_CONTRACT_CHANGE_REQUIRED`，不得自行繞過凍結契約。

## 2. 原始來源與逐頁身分

`source_digest = SHA-256(original raw PDF bytes)`，以小寫 64 位 hex 表示，是唯一 canonical source digest。Raster/image bytes、OCR 文字、暫存檔或 renderer path 都不得取代它。所有頁面保留同一原始 `source_id` 與 `source_digest`。

OCR locator 沿用 Phase 15.1：`{"kind": "page", "page": 1, "total_pages": 42}`。Phase 15.2 必須取得完整頁數並在每筆 OCR locator 記錄 `total_pages`；`page` 是 1-based 原始來源頁碼，不是 OCR 子集合順位，不接受 boolean。要求 `1 <= page <= total_pages`，不同 parser／renderer 頁數不一致時拒絕處理。禁止透過 raster filename 推算頁碼。

這不改變 Phase 15.1 通用 locator 的 optional total_pages 規則。搜尋文字的既有 Phase 13 locator 仍為 start/end；兩類證據保持分離，不把 OCR locator 送入 Phase 12 validator。轉換屬 Phase 15.5。

## 3. Renderer 與版本政策

架構選定 **PyMuPDF** 為預設本機 PDF raster adapter，支援目標限定 **1.24.x（>=1.24.0,<1.25.0）**，不是 unbounded latest。實作／發布環境必須在範圍內審查並釘選確切 patch 與對應 MuPDF build；版本不可確定、超出範圍或無可核准的安全 patch 時不得執行，需重新治理版本政策，不能靜默升級。

[PyMuPDF 1.24.14 package metadata](https://pypi.org/project/PyMuPDF/1.24.14/) 宣告 Python >=3.9，提供 CPython 3.9+ ABI wheels（macOS Intel／Apple Silicon 與 Linux），可涵蓋本庫 Python 3.11 驗證基線；此為套件相容性證據，不是所有平台實測或安全認證。

PyMuPDF／MuPDF 採 AGPL 或 Artifex commercial license；本庫 MIT 不會消除依賴授權義務。架構選定不等於完成授權審查或取得商業授權。Phase 15.2-C 新增依賴前，正常 dependency/security review MUST 明確記錄使用／散布模式的授權合規路徑、版本風險與平台支援，更新所需 notices。若無法符合，停止回報 renderer 授權／依賴 blocker，不得默換引擎。本文件不安裝套件、不改 requirements。

必要 PR contract CI 使用 fake rasterizer，不依賴可變動的 host renderer；真實 renderer 驗證另屬 opt-in live/release validation，遵循 Phase 15.6 邊界。

## 4. 固定 raster 設定

| 設定 | Phase 15.2 預設契約 |
| --- | --- |
| dpi | 300 |
| output_format | PNG |
| colorspace | RGB |
| alpha | false |
| rotation_policy | respect_effective_pdf_page_rotation |
| box_policy | valid_explicit_cropbox_else_mediabox |
| semantic_preprocessing | none |

Effective rotation 依 PDF 有效（含繼承）頁面 rotation，正規化為 0／90／180／270 度；不得用 OCR orientation 或猜測修正。CropBox 的明確定義包含 PDF 合法繼承值：必須為有限座標、正面積且位於有效 MediaBox 內。缺漏或無效 CropBox 使用 MediaBox，不得讓 renderer 自動裁切政策取代此決策。MediaBox 無效或 rotation 不合法視為無效 PDF 輸入。頁框先選定，再套用有效 rotation；像素尺寸取 300 DPI 轉換後的向外整數邊界，並驗證實際輸出尺寸。

這些均為機械執行設定；不做 deskew、denoise、threshold、文字修補、語意 crop 或品質預測。不建立 force_ocr 覆寫；此功能需後續顯式契約。

## 5. Raster provenance

Phase 15.2 orchestration 擁有逐 scanned page 的 `raster_provenance`，以原始 OCR-native locator 關聯該頁的 Phase 15.1 OCREvidence，置於 additive PDF transaction envelope；不擴充 Phase 13 ExtractionResult，不要求改動 Phase 15.1 provider evidence 結構。每頁保留完整 provider evidence，不將不同 provider／fallback 的頁面合併成虛構的共同 provider provenance。這是文件資料模型，不發布 JSON schema。

| 必要欄位 | 意義 |
| --- | --- |
| renderer_id | pymupdf |
| renderer_version | 實際確切 PyMuPDF patch |
| renderer_engine_version | 實際 MuPDF version/build identity |
| dpi、output_format、colorspace、alpha | 實際有效固定設定 |
| rotation_policy、box_policy | 第 4 節固定政策名稱 |
| effective_rotation、selected_box、box_coordinates | 實際角度、CropBox／MediaBox 與原始 PDF 座標 |
| width、height | 實際 raster 像素尺寸 |
| raster_digest | SHA-256(actual prepared raster bytes supplied to OCR)，小寫 64 位 hex |

`raster_digest != source_digest` 表示兩者角色與被雜湊的 bytes 不同，不是要求用 digest 不相等作驗證。Raster digest 僅為衍生準備步驟 provenance，不是來源身分或語意權威。雜湊必須針對實際傳給 OCR 的 PNG bytes；不得雜湊另一份 preview 或重新編碼版本。Provider fallback 使用同一份已驗證 raster。

Canonical provenance 排除 temporary path、host cache path、absolute renderer path、timestamps 與任意 environment dump；不得填入 unknown。Phase 15.2 不引入 persistent raster cache／reuse，不需要公開 `OCR_RASTER_CHANGED`。未來 caching 的 staleness／invalidation 必須另行設計。

## 6. 機械分類與 mixed-PDF 路由

對每個原始頁面使用 Phase 13 的 deterministic pypdf page text extraction 語義（`page.extract_text() or ""`）。**只為分類**測試 `extracted_text.strip()`：非空為 SEARCHABLE，空字串或 Unicode whitespace-only 為 SCANNED；不改寫實際擷取文字。

現有 frozen Phase 13 `extract_pdf` 會正規化換行／strip、略過空頁，且全文件無文字時拋出 SourceTextUnavailable。不得將其 compact blocks 當成完整 page model 或吞掉 extraction error 判為 scanned。Additive Phase 15.2 必須取得含空頁的 pypdf page model，沿用同一擷取規則；SEARCHABLE 保留 Phase 13 既有文字／locator／block 行為，不新增文字正規化。原有 Phase 13 API 與錯誤完全保留；新 PDF OCR entrypoint 才處理全掃描文件。

頁面按原始 `1..total_pages` 順序執行：

| 分類 | 路徑 |
| --- | --- |
| SEARCHABLE | 保留 deterministic text-extraction path，不 rasterize、不呼叫 OCR |
| SCANNED | 資源驗證 → 固定 rasterization → 有效 raster → Phase 15.1 provider resolution/execution → canonical evidence validation |

禁止語意分類、image-area heuristic、字數／語言門檻、LLM judgment 或 OCR 品質預測。有少量非空白文字及大圖片的頁面仍是 SEARCHABLE，不自動 OCR；抽取失敗是失敗，不是 SCANNED。未來品質式 fallback 須新契約。

Additive transaction page entries 包含每一原始頁面的順序、分類及其既有文字結果或完整 OCR evidence／raster provenance；OCR evidence 子集合仍依原始頁碼升序，不補造 searchable 頁面的 OCR。空白 scanned page 若 provider 有效辨識為空，沿用 `OCR_TEXT_UNAVAILABLE` 警告、保留空 raw_text 與該頁；不是省略或 partial success。

## 7. Fail-closed transaction 與 encrypted PDF

逐頁循序執行，不並行競速決定第一個錯誤。先完成文件 parse/readability/page-count 驗證，再逐頁依分類、資源預檢、render、raster 驗證、provider execution、evidence validation 的固定順序處理。任一必要 scanned page 在上述步驟失敗，整個 PDF OCR transaction 失敗；SEARCHABLE extraction error 同樣失敗。不得發布看似完整的部分結果；全部頁面驗證與暫存清理成功後才交付 transaction evidence。

診斷保留第一個失敗的原始頁碼、stage、stable code 與已有 cause 順序；不執行後續頁面。文件級失敗沒有虛構頁碼；cleanup 次要錯誤不得覆蓋原始錯誤。不得含私有路徑、原始文件內容或任意 stderr。未來 partial-success 契約須另外治理。

不取得、儲存、提示或猜測密碼。需要使用者密碼才能存取／render 必要頁面時，以 `OCR_PDF_PASSWORD_REQUIRED` deterministic unsupported input 失敗。僅標記 encrypted、但 parser／renderer 都已驗證不需使用者 credentials 即完全可讀者可正常處理；不得僅依 encrypted flag 拒絕或假設 readable。

## 8. 資源上限與安全邊界

所有限制 MUST 在 production 明確執行，不能只於產物完成後檢查。以下是初始保守 ceiling，非容量／效能實測承諾；不得因 host 可用資源而自動放寬。實作可設定更低上限，須在診斷記錄有效限制，超出本契約 ceiling 需另行治理。

| 資源 | 預設最大值 |
| --- | --- |
| 原始 PDF bytes | 100 MiB |
| total_pages | 500 |
| raster width／height | 各 10,000 px |
| pixels per page | 25,000,000 |
| PNG raster bytes per page | 100 MiB |
| renderer wall-clock timeout | 每頁 30 秒，含 encode／驗證；不自動重試 |
| 文件開啟／頁數驗證 | 30 秒 |
| 每頁文字抽取 | 30 秒 |
| transaction 暫存儲存同時占用 | 256 MiB，包含此流程與 provider-owned 暫存內容 |
| PDF parser／renderer worker memory | 每個 worker 512 MiB |

MiB = 1,048,576 bytes。將提案的 100,000,000 pixels 降至 25,000,000，因 RGB 原始 buffer 已需約 75 MB（原提案約 300 MB），尚未含 native renderer、encode 與 copy；25M 仍涵蓋一般 A3 300 DPI 約 17.4M pixels。width／height／pixel product 必須全部符合。256 MiB 暫存上限配合每次一頁、100 MiB PNG ceiling，不允許累積 500 頁 raster；下一頁開始前清理前頁 raster。超額即 fail closed，不能降 DPI、截頁或默換設定。

頁框／rotation 推算尺寸須在配置 pixel buffer 前驗證；實際 PNG bytes 與 decode 結果也須有界驗證。暫存寫入與 native allocation 需有真正的 quota／隔離限制。既有 Phase 15.1 provider timeout 仍適用，30 秒 renderer timeout 不覆蓋它。

禁止 shell execution；只使用安全 API 或固定 executable 加獨立 argv，無網路需求、不下載模型／renderer，不帶 credentials。PyMuPDF 即使用 in-process library API，仍屬 untrusted-input processing；native 呼叫須在可終止、受 memory/time/storage 限制的 worker 邊界內，不能用無法中止的 thread timeout 宣稱已強制限制。平台無法強制任一上限時，啟動前以資源限制錯誤拒絕，不能 best-effort 繼續。

僅清理本 transaction 擁有的暫存 raster／資源，成功、失敗、timeout 皆須 finally cleanup；不得刪除原始來源。不得保留 persistent raster cache。

## 9. Orchestration error taxonomy 與 fallback

下列是 Phase 15.2 公開 orchestration-layer 代碼的文件契約，尚未實作；既有 Phase 15.1 provider errors 不改動。

| 代碼 | 條件 |
| --- | --- |
| OCR_PDF_PASSWORD_REQUIRED | 必要頁面需要使用者密碼；unsupported input |
| OCR_PDF_INPUT_INVALID | 無法解析 PDF、page text extraction 失敗、無效 MediaBox／rotation、零頁或 parser／renderer 頁數不一致 |
| OCR_PDF_PAGE_INVALID | 要求頁碼非正整數（含 boolean）或超出已驗證 total_pages |
| OCR_PDF_RESOURCE_LIMIT_EXCEEDED | 任一明確 byte/page/pixel/time/memory/storage ceiling 超限，或無法強制必要 resource controls |
| OCR_PDF_CLEANUP_FAILED | 無既有主要錯誤時，無法清理本 transaction 暫存資源；不得交付成功 |
| OCR_RASTERIZATION_FAILED | 設定的 dependency resolution 後 renderer 不可用、版本不可確定／不受支援、render execution failure 或無效 raster output／必要 raster provenance |

已知資源超限（包括 renderer timeout）優先使用 RESOURCE_LIMIT_EXCEEDED，不包成 RASTERIZATION_FAILED；無法解析／密碼／無效 page request 也不映射為 provider error。固定資源預檢順序為原始 bytes、頁數、寬、高、pixels、memory/storage 可強制性；執行期保留最先觀察的 stage failure，列出的次要診斷按頁碼及 stage 排序。相同輸入與相同觀察到的失敗保證排序；不保證不同 host load 下 timeout 結果一致。

Rasterization 在 provider fallback **之外**：raster failure → Phase 15.2 failure → **NO provider fallback**，不轉成 OCR_FALLBACK_NOT_ALLOWED。有效 prepared image 存在後才套用 Phase 15.1 selection／fallback：預設 disabled，只有操作性 provider failures 可顯式 fallback，terminal errors 永不 fallback，每次頁面 provider invocation 最多一次 explicit fallback，無文件級重跑／fallback loop。

`OCR_SOURCE_CHANGED` 僅為 original raw PDF bytes 改變；`OCR_MODEL_CHANGED` 僅為 OCR model/traineddata identity 改變；raster_digest 是衍生 provenance。不得借用 SOURCE_CHANGED、MODEL_CHANGED 或 PROVIDER_FAILED 表示 raster／PDF input／resource 錯誤。無 raster cache/reuse，故本階段不新增 OCR_RASTER_CHANGED。

## 10. 確定性聲明與 CI

保證 deterministic page ordering、機械 classification、locator values、raster configuration、orchestration order、evidence ordering、failure ordering 與 canonical provenance structure。分類依固定 extraction 實作與已審查依賴環境；不得把不同 pypdf 版本行為假設相同。保留 renderer、MuPDF、OCR provider／engine／model versions 與模型 digest。

不宣稱跨平台 pixel-identical rendering，也不宣稱不同 OCR engine/model builds bit-identical output。raster_digest 識別該次實際 PNG，不是跨平台相等承諾。

Required PR deterministic CI MUST 使用 fake rasterizer、fake OCR provider、deterministic synthetic PDF fixtures/page models，覆蓋分類（含 whitespace、稀疏文字、大圖、空頁）、資源邊界、順序／失敗、source identity／locator／raster provenance、encrypted-readable／password-required 以及 cleanup。不得依賴 mutable host Tesseract accuracy、真實 renderer pixel equivalence、網路或 AI 額度。

Real PyMuPDF + Tesseract 測試只在另行 opt-in live/release validation 中執行，與 Phase 15.6 真實來源 production validation 一致；不能以 fake CI PASS 宣稱真實引擎已通過發布驗證。本次不修改 CI／tests。

## 11. 逐增量實作 gate

| 增量 | 範圍與限制 |
| --- | --- |
| Phase 15.2-A | Contracts、resource limits、deterministic fake rasterizer/provider、identity/error models；無 real renderer |
| Phase 15.2-B | Mechanical searchable/scanned classification、mixed-PDF ordering；無語意 heuristic |
| Phase 15.2-C | 經 dependency/security/license review 的 PyMuPDF adapter、raster provenance、resource enforcement；無 OCR orchestration |
| Phase 15.2-D | Scanned-page raster → Phase 15.1 OCRProvider orchestration、evidence ordering、fail-closed transaction；無 Phase 12 grounding |
| Phase 15.2-E | Contract consolidation、文件、full validation、PR readiness |

每個增量的確切 GitHub contexts **`deterministic`** 與 **`repository`** 必須在該增量最新 commit **PASS**，下一增量才可開始。不得以 child jobs、歷史 PASS 或本機測試取代。此文件 PR 不啟動 A，也不代表 Phase 15.2 已實作；Phase 15.2 維持 **NOT STARTED**，OCR schemas 維持 **DEFERRED**。
