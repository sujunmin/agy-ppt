# Source Grounding & Traceability（Phase 12.1 + 12.2）

本文件描述 Phase 12 建立的 source-grounding sidecar 系統。這是 **optional
capability**：純創意、無 source document 的簡報完全不受影響，也不需要建立任何
本文件描述的 artifact。

## 1. 與 v0.1.0 baseline 的關係

`docs/production-baseline-v0.1.0.md` 是 immutable 的歷史 baseline 文件，記錄
v0.1.0 release 當時「source traceability」「source-grounded QA」尚未有 reusable
production 實作。本文件記錄的是 v0.1.0 **之後** 新增的能力，不會、也不應該回頭
修改 v0.1.0 baseline 文件本身。

## 2. 核心設計原則：兩層分離

Source grounding 拆成兩層，**不得混淆**：

### Layer A — Semantic Evidence Creation（AGY 擁有）

AGY 負責：

- 理解 source document
- 定義 source units（要拆成哪些段落/頁面/條款）
- 判斷某個 slide claim 對應哪個/哪些 source unit
- 判斷該 claim 是否真的被 source 支持（`support_status`）
- 判斷 source unit 的 coverage priority（`HIGH` / `MEDIUM` / `LOW`）
- 判斷數字、模態語言（must/may/shall...）、權責歸屬的語意
- 產生 traceability evidence 並持久化

### Layer B — Deterministic Contract Validation（`scripts/source_grounding.py`）

Python 負責：

- schema 形狀驗證
- ID 唯一性、可推導性（`unit_id` 必須能從 `source_id` + `locator` 重新算出來）
- 參照完整性（`claim_traceability.json` 裡的 `source_unit_ids` 必須真的存在於
  `source_inventory.json`；`slide_id` 必須真的存在於 `project_state.json`）
- HIGH priority source unit 的 coverage accounting 完整性（不能默默消失）
- 合法 status 值檢查
- resume-safe 的 atomic 持久化

**Python 永遠不會**：

- 自己判斷一個 claim 是否為真
- 自己理解契約/文件的語意
- 取代 AGY 的 Content QA 或 source understanding
- 取代既有的 Visual QA（`generated -> qa_passed/qa_failed`）

## 3. 四個 sidecar Artifact

全部存在 workspace 根目錄，與 `project_state.json` 同層（`prompts/slide_XX.json`
的相同 pattern：additive，不複製、不取代）：

| 檔案 | Schema | 目的 |
| --- | --- | --- |
| `source_inventory.json` | `schemas/source_inventory.schema.json` | 把 source document 拆成穩定的 source units |
| `claim_traceability.json` | `schemas/claim_traceability.schema.json` | 記錄每個 slide claim 對應哪些 source unit，以及 AGY 的支持判斷 |
| `source_coverage.json` | `schemas/source_coverage.schema.json` | 每個 source unit 的 deterministic accounting |
| `source_grounded_qa.json` | `schemas/source_grounded_qa.schema.json` | 最終報告，明確拆成 `deterministic_findings` 與 `semantic_findings` 兩個區塊 |

## 4. Optional Capability

`source_inventory.json` 不存在，或存在但 `enabled: false`，代表這個專案**沒有**
啟用 source grounding：

```python
from source_grounding import source_grounding_enabled
source_grounding_enabled(workspace_root)  # False when file absent or enabled=false
```

在這個狀態下：

- 不需要 `claim_traceability.json` / `source_coverage.json` /
  `source_grounded_qa.json`
- `assembly_precondition_errors()` 一律回傳空陣列（不 block 組裝）
- `project_state.py` 完全不知道、也不需要知道這個模組存在

## 5. Stable IDs

| ID | 格式 | 推導方式 |
| --- | --- | --- |
| `source_id` | `src_<caller-supplied-slug>` | AGY 提供，人類可讀，不含絕對路徑 |
| `unit_id` | `su:<source_id>:<12-hex>` | `compute_unit_id(source_id, locator)`：對 `(source_id, canonical_json(locator))` 取 sha256 前 12 hex，deterministic、resume-safe，重新計算永遠得到相同值 |
| `claim_id` | `cl:<slide_id>:<NN>` | `make_claim_id(slide_id, sequence)`，deterministic |

沒有任何 ID 使用 random UUID 作為唯一身分，也沒有任何 ID 包含 OS 絕對路徑。

## 6. Source Locator Contract

`locator` 是一個可擴充的 tagged union，**不綁死 OS 絕對檔案路徑**：

```json
{"kind": "page", "start": 12, "end": 12}
{"kind": "section", "label": "Termination"}
{"kind": "line_range", "start": 40, "end": 55}
{"kind": "generic", "label": "Appendix B"}
```

Phase 12.1/12.2 只定義 contract，不內建 PDF/DOCX/Markdown parser；未來若要自動
從真實文件產生這些 locator，屬於後續 Phase 的工作。

## 7. Source Privacy

- `source_digest` 只存 sha256 hex digest（`compute_source_digest()`），**永遠
  不存來源文件的原文**。
- `source_changed(source_id, current_digest)` 用來偵測來源是否已更動；偵測到
  改變後是否要作廢舊的 traceability evidence，是呼叫端（AGY/未來的 workflow
  整合）的明確決策，本模組只提供 `SourceChanged` 這個 error class 供呼叫端使用，
  不會自動、悄悄地沿用過期 evidence。
- Metadata 中任何 credential-shaped key（`api_key`、`access_token` 等）會被
  `validate_source_inventory()` / `validate_claim_traceability()` /
  `validate_source_coverage()` / `validate_source_grounded_qa()` 拒絕，與
  `project_state.py` 的 `_reject_credentials` 精神一致（各自獨立實作，未共用
  import，避免 sidecar 與 frozen 核心互相耦合）。

## 8. 錯誤代碼

```text
SOURCE_INVENTORY_INVALID
TRACEABILITY_INVALID
SOURCE_REFERENCE_MISSING
SOURCE_COVERAGE_INCOMPLETE
GROUNDED_QA_INCOMPLETE
SOURCE_CHANGED
```

這些是獨立的 error 家族，**與** `IMAGE_GENERATION_FAILED`、
`IMAGE_BACKEND_UNAVAILABLE` 等 worker/image error **完全分離**；不共用同一個
retry/block policy。Phase 10.2/10.3 的「連續兩次相同 image failure 即 block」
語意不因本模組而改變。

## 9. Assembly Gate（deterministic precondition，尚未整合進 workflow）

`assembly_precondition_errors(workspace_root, known_slide_ids)` 提供一組
deterministic 檢查：

- source grounding 未啟用 → 一律回傳 `[]`（不 block）
- 已啟用時：
  - `claim_traceability.json` / `source_coverage.json` 結構或參照無效 → 回傳
    對應錯誤訊息
  - 任何 HIGH priority source unit 的 `coverage_status` 仍是 `unaccounted`
    → 回傳錯誤訊息

**這是 Phase 12.1/12.2 的 contract，尚未被接到任何實際的組裝流程或
`assemble_ppt.py` 呼叫路徑中。** 是否、以及如何在 workflow 的哪個階段呼叫這個
函式，是 Phase 12.3（AGY workflow 整合）要決定的事，本階段刻意不動
`assemble_ppt.py`（frozen，且本身運作正常）。

## 10. Content QA vs Visual QA

- **Content QA**：claim support、source grounding、數字/模態語言 fidelity、
  coverage——由本模組的 artifact 承載 AGY 的判斷，deterministic validator 只
  驗證形狀與參照完整性。
- **Visual QA**：視覺品質、版式、渲染、圖片正確性——由
  `project_state.py` 既有的 `generated -> qa_passed/qa_failed` state machine
  處理，**完全不受本模組影響**。

`source_grounded_qa.json` 的 `semantic_findings.agy_qa_outcome` 是 Content QA
的持久化結果，與 slide 的 Visual QA 狀態是兩個獨立的欄位、獨立的檔案，永遠不會
互相覆寫。

## 11. Numeric / Modal Fidelity

`claim_traceability.json` 每個 claim 可以附帶：

```json
"numeric_evidence": {
  "source_value": "90 days",
  "slide_value": "90 天",
  "unit": "days",
  "comparison_status": "match"
}
```

```json
"modal_evidence": {
  "source_modality": "shall",
  "slide_modality": "must",
  "responsible_party": "Vendor",
  "comparison_status": "match"
}
```

`comparison_status` 的值（`match` / `mismatch` / `not_comparable`）由 AGY 提供
並持久化。Deterministic validator 只驗證這個欄位是否為合法列舉值，**不會**
自己解析或比較數字/法律語意——避免用脆弱的 regex 假裝理解整份文件。

## 12. Speaker Notes

`assemble_ppt.py` 既有、frozen 的 `speech.md` → PPTX notes 寫入機制未被修改。
若未來要讓 speaker-note claims 也進入 traceability，屬於 Phase 12.3 的最小
整合工作，不在本階段範圍。

## 13. 尚未完成的部分（Phase 12.3 / 12.4）

- AGY workflow 各階段何時建立/更新這些 artifact（intake / outline / slide
  generation / Content QA / assembly / complete）尚未整合進 `SKILL.md` 的
  正常簡報流程。
- 尚未對真實（非 confidential 測試用）source document 執行過 live 驗證。
- 尚未有任何 CLI/prompt 指示 AGY 在什麼時機呼叫
  `SourceInventory` / `ClaimTraceability` / `SourceCoverage` 的 API。

這些留給 Phase 12.3（AGY workflow 整合）與 Phase 12.4（真實 source 驗證），
本次任務範圍只到 Phase 12.1（contract/schema/error taxonomy）+ 12.2
（deterministic validator + resume/change-detection 行為 + tests）。
