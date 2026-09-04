---
name: agy-ppt
description: 以 AGY 為唯一主控，Kiro 負責所有程式工程，Codex 僅透過 built-in $imagegen 產生或編修整頁簡報圖片的圖片式 PPT/PPTX 工作流程。
---
# AGY PPT Orchestrator

## 1. 目的

本 Skill 建立在 `codex-ppt-skill` 的成熟圖片式 PPT 流程之上，但重新定義 Agent ownership。

每張投影片以完整 16:9 圖片呈現，最後使用既有 deterministic script（例如 `scripts/assemble_ppt.py`）組裝為 `.pptx`。

本 Skill 的最高層規則是：

```text
AGY   = 唯一主控 / 簡報導演 / workflow source of truth
Kiro  = 工程師 / Skill 維護者 / 所有 executable code change owner
Codex = 圖片 renderer / editor only
既有 scripts = AGY 可以執行，但只有 Kiro 可以修改
```

任何上游檔案若與本檔案的 ownership、routing、backend 或 OAuth policy 衝突，以本檔案與 `docs/agent-routing.md` 為準。

## 2. 核心設計原則

### 2.1 單一控制者

工作流程永遠遵守：

```text
AGY -> worker -> AGY
```

Kiro 與 Codex 不得互相直接交接，也不得自行決定下一個 workflow phase。

### 2.2 AGY 負責「要做什麼」

AGY 擁有：

- 使用者需求理解
- 受眾與簡報目的
- 大綱、頁數、storyline
- `outline.md`
- 視覺方向與版式策略
- `deck_spec.json`
- slide jobs / state
- 每頁文案、資訊層級、圖片 prompt
- approval gates
- content QA / visual QA
- speaker notes
- 是否接受 worker 結果
- 是否重生圖片
- 是否進入組裝與完成階段

### 2.3 Kiro 負責「如何讓系統做到」

只要任務需要：

- 寫程式
- 改程式
- debug
- 新增功能
- 改 executable workflow logic
- Python / JS / TS / Shell / PowerShell
- CLI adapter / ACP adapter
- schema/tool contract 修改
- filesystem processing
- PPTX assembly implementation
- validator
- dependency/build 修復
- tests / fixtures / regression test

一律由 AGY 派給 Kiro。

AGY 可以執行已存在且已驗證的 script，但不得因為自己有能力就直接修改程式碼。

### 2.4 Codex 只負責圖片

Codex 可以：

- 生成一張樣張
- 生成指定的一張正式投影片圖片
- 編修／重生指定投影片圖片
- 回傳簡短 renderer QA note

Codex 不得：

- 改 `outline.md`
- 改 `deck_spec.json`
- 改 slide job
- 重寫文案或事實
- 增減頁數
- 改整份簡報策略
- 寫或改程式
- 組裝 PPTX
- 自行換 image backend
- 使用 Pillow / SVG / HTML / CSS / Canvas / python-pptx / PptxGenJS 假裝成 AI 生圖

## 3. OAuth-only 執行原則

本 workflow 假設三個 CLI 都已經用各自訂閱方案登入：

```text
AGY   -> Google AI Pro session
Kiro  -> Kiro Pro session
Codex -> ChatGPT Plus / Codex session
```

Skill 不管理、不複製、不讀取、不轉傳 OAuth access token / refresh token。

預設不要求：

- `GEMINI_API_KEY`
- `KIRO_API_KEY`
- `OPENAI_API_KEY`
- `CODEX_API_KEY`

## 4. 固定圖片後端

正常路徑固定為：

```text
AGY
  -> codex_image_adapter.py
  -> Codex CLI          codex exec --json --skip-git-repo-check   (prompt 走 stdin)
  -> $imagegen
  -> built-in image_gen
  -> $CODEX_HOME/generated_images/<thread_id>/<artifact>.png
  -> 驗證 + copy 進 workspace output_path
  -> AGY QA
```

Codex 圖片派工由 `scripts/codex_image_adapter.py` 實作，backend 固定為
`codex_builtin_imagegen`，operation 第一版支援 `generate` / `regenerate` / `probe`。

不得自動改用上游的 `scripts/image_gen.py`、第三方 API 或其他付費 image backend。
adapter 會從 Codex 子行程環境移除 API-key 類變數，避免 silent API fallback。

若 Codex 當前 session 沒有暴露 built-in `image_gen`，回報：

```text
IMAGE_BACKEND_UNAVAILABLE
```

並將控制權交回 AGY。其他 renderer 失敗（`CODEX_CLI_UNAVAILABLE`、
`CODEX_AUTH_UNAVAILABLE`、`IMAGE_GENERATION_FAILED`、`IMAGE_ARTIFACT_NOT_FOUND`、
`IMAGE_OUTPUT_INVALID`、`IMAGE_OUTPUT_PATH_CONFLICT`、`CODEX_TIMEOUT`）同樣交回 AGY，
不自動 fallback 付費 API。細節見 `docs/codex-image-runtime.md`。

## 5. Kiro 呼叫原則

Kiro custom agent 名稱：

```text
ppt-engineer
```

放在：

```text
<repo>/.kiro/agents/ppt-engineer.md
```

### 5.1 Kiro Runtime

唯一受支援：

```text
Kiro CLI V3
```

正式啟動：

```bash
kiro-cli --v3 acp --auth-method cli
```

ACP over stdin/stdout，使用 JSON-RPC 2.0。

- Agent：`ppt-engineer`
- Agent selection：`session/set_mode`
- Agent confirmation：`config_option_update` / `current_mode_update`
- V2：**不支援**，不得 fallback

V3 的 `acp` 子指令不接受 `--agent`，因此 `ppt-engineer` 必須在 ACP session 內切換。

`--auth-method cli` 讓 kiro-cli 自己解析 access token。省略時 V3 引擎會要求 ACP client
代為提供 token，這是本 Skill 禁止的行為。

舊 caller 若仍送出 `engine = "v2"`，一律回報並拒絕執行：

```text
UNSUPPORTED_KIRO_ENGINE
```

### 5.2 正式流程

```text
AGY
  -> kiro_acp_bridge.py
  -> Kiro CLI V3 ACP
  -> 使用既有 Kiro Pro CLI OAuth session
  -> session/new
  -> 發現 ppt-engineer
  -> session/set_mode
  -> 確認 agent scope
  -> engineering task
  -> permission enforcement
  -> TurnEnd
  -> AGY
```

派工使用：

```bash
python3 scripts/kiro_acp_bridge.py --input job.json
```

AGY 送出的工程任務至少包含：

- repository root
- 問題或需求
- 可修改範圍
- acceptance criteria
- 要跑的 tests/checks
- 禁止自行改簡報內容與視覺策略
- 完成後必須回 AGY

### 5.3 Agent selection 與 scope

`session/set_mode` 請求：

```json
{"method": "session/set_mode", "params": {"sessionId": "...", "modeId": "ppt-engineer"}}
```

`session/set_mode` 即使 `modeId` 不存在也會回傳空結果，所以不得把 response 當成成功證據。
唯一確認來源是引擎回報的 active agent：`session/update` 的 `config_option_update`
（`configOptions[id="mode"].currentValue`），或標準 `current_mode_update`。

dispatch 前必須滿足：

```text
diagnostics.agent_requested = "ppt-engineer"
diagnostics.agent_resolved  = true
diagnostics.agent_scoped    = true
```

不成立時不得送出 coding task，回報：

```text
ENGINEERING_AGENT_UNAVAILABLE
```

不得默默使用 `kiro_default` 或任何引擎預設 agent 執行 AGY 的 engineering task。

### 5.4 Agent scope 是 turn-long invariant

`ppt-engineer` 必須是整個 engineering turn 的 runtime invariant。

從 `session/prompt` 送出，到 `stopReason = end_turn` 之前，只要任何 ACP event 顯示
active agent 已不是 `ppt-engineer`，即視為 agent scope loss：

1. 記錄 diagnostics
2. timeline 加入 `agent_scope_lost`
3. 停止批准新的 permission request
4. `session/cancel`
5. 套用既有 cancel grace period
6. 清理 child process group
7. 回報 `ENGINEERING_AGENT_SCOPE_LOST`

不得自動切回 `ppt-engineer` 後繼續、不得繼續批准 tool call、不得判定 completed、
不得 silently restart。

### 5.5 失敗回報

```text
ENGINEERING_WORKER_UNAVAILABLE   Kiro 無法啟動或 ACP handshake 失敗
ENGINEERING_AGENT_UNAVAILABLE    worker 可連線但 agent scope 無法確認
ENGINEERING_AGENT_SCOPE_LOST     turn 中 active agent 漂移
UNSUPPORTED_KIRO_ENGINE          caller 要求非 V3 engine
```

都不得偷偷切 API key，也不得由 AGY 接手寫 code。

### 5.6 Permission boundary

`.kiro/agents/ppt-engineer.md` 定義 Agent 能力。
`scripts/kiro_acp_bridge.py` 定義 runtime enforcement。
兩者衝突時採**較嚴格者**。

允許：

- 讀取專案檔案
- 寫入 repository root 內的檔案
- `python` / `python3` / `pytest`（含 `-m unittest`、既有 script）
- `pip list` / `pip show` / `pip check`

拒絕並記錄到 `policy_violations`：

- 版本控制（本工程 Worker 不提供 Git 能力）
- shell chaining / pipeline / command substitution（`&&`、`||`、`;`、backtick、`$()`）
- `sudo`、destructive filesystem 命令、未授權 package execution
- repository root 之外的寫入
- dependency / lockfile 變更（預設需額外授權）
- `codex`、`$imagegen`、`image_gen`（永久拒絕）

Dependency 變更預設關閉：

```json
{"allow_dependency_changes": false}
```

未取得 explicit opt-in 時 reject，並記錄：

```text
dependency_change_requires_explicit_authorization
```

`true` 只代表通過 dependency gate，仍必須通過 shell parser、command safety、
workspace policy 與 permission mode。

Kiro 永遠不得自行呼叫 Codex。

## 6. 正常簡報流程

1. AGY 讀取來源資料。
2. AGY 決定 audience、objective、page count、storyline。
3. AGY 建立並確認 `outline.md`。
4. AGY 決定視覺風格與 required assets。
5. AGY 建立 sample slide job。
6. AGY 派 Codex 生成 1 張樣張。
7. AGY 做最終 QA，必要時讓使用者確認樣張。
8. AGY 使用既有 upstream scripts 初始化專案與 jobs。
9. AGY 逐頁派 Codex 產圖。
10. 每個 Codex worker 完成後都回 AGY。
11. AGY 檢查文字、事實、版式、required assets、風格一致性。
12. 不合格的頁面由 AGY 下達精準修正 job，再交 Codex。
13. AGY 產生 `speech.md`。
14. AGY 執行既有 `assemble_ppt.py`。
15. AGY 驗證最終 `.pptx`、頁數與 notes。
16. AGY 回報產物。

### 6.1 文字密度與 Visual QA 原則

1. **不設定固定字數上限**：AGY 不得單純因為文字超過某個固定字數，就強制拆頁、刪除文字、縮寫內容、改寫權威文案（authoritative text）或遺漏條件說明。文字內容完整性永遠優先。
2. **實績驗證範圍**：Phase 8A 實測已驗證目前系統至少能穩定處理約 79～239 字／頁的高密度繁體中文內容（此為已驗證成功範圍，而非系統硬性上限）。不建立硬性 240 / 300 字門檻，更高文字量依實際 Visual QA 判斷。
3. **以 Visual QA 決定是否需要拆頁**：只要生成後的圖片符合：
   - authoritative text 完整且文字完全正確
   - 字級清楚可讀、無裁切、無重疊
   - 換行合理、層級清楚
   - 版面仍具備合理留白與可接受的整體閱讀負荷
   即可判定 `qa_passed`。不得僅因為「文字很多」本身判定失敗。
4. **高文字量優先調整版型**：若單頁文字量較高，AGY 應在 prompt 與版面策略上優先考慮雙欄、2×2、2×3、多區塊卡片、比較矩陣、Checklist、流程、階梯、Framework 等分區架構，避免預設使用容易擁擠的單欄長條列。
5. **Regenerate 優先於拆頁**：若內容完整但第一版排版太擠、字級過小、間距不足或閱讀動線不佳，先由 AGY 判定 `generated -> qa_failed -> ready -> regenerate`，要求 Codex 採用更適合高資訊密度的版型。只有當 AGY 判斷「在維持完整文字與可讀性的前提下，單頁確實無法合理容納」時，才允許拆頁。

## 7. 工程例外流程

正常簡報製作不需要每次經過 Kiro。

只有出現工程需求時：

```text
AGY 發現 coding/tooling 問題
  ↓
定義工程需求與 acceptance criteria
  ↓
Kiro 修改 / debug / test
  ↓
Kiro 回報
  ↓
AGY 驗收
  ↓
AGY 回到原本簡報流程
```

## 8. 既有指令碼規則

AGY 可以執行已存在的：

- `scripts/assemble_ppt.py`
- `scripts/prepare_slide_prompts.py`
- `scripts/kiro_acp_bridge.py`
- state / dispatch / result scripts
- runtime bootstrap / validation helpers

若上述 script 需要新增、修改、修復或測試，必須交給 Kiro。

## 9. 狀態 ownership

全域 workflow state 只能由 AGY 決定。

Codex 只能回 renderer result。

Kiro 只能回 engineering result。

Worker 不得把自己的區域性狀態當成整份簡報的真實狀態。

AGY 專用的 deterministic project state 記錄在 `<workspace>/project_state.json`，
由 `scripts/project_state.py` / `scripts/validate_project.py` 操作：

- deck phase 機：`intake -> outline -> style -> sample -> slide_generation ->
  visual_qa -> assembly -> complete`，任何 phase 可 `-> blocked`。
- slide state 機：`planned -> ready -> generating -> generated ->
  qa_passed/qa_failed -> assembled`，`generation_failed` 可退回 `ready` 重生。
- `controller` 永遠 `agy`；`sequential_only` 永遠 `true`（第一版）。
- Codex 回 `generated` **不等於** `qa_passed`；只有 AGY 能做 `generated -> qa_passed`。
- worker result 不得寫 project phase；generation counter、attempt history、
  resume/recovery、idempotency、corrupt-state 保護、path safety 皆為 deterministic。
- 禁止 worker chain（`AGY -> Kiro -> Codex`、`AGY -> Codex -> Kiro`）。

詳見 `docs/runtime-state-and-routing.md`。

Schema：`schemas/project_state.schema.json`、`schemas/slide_job.schema.json`、
`schemas/worker_result.schema.json`。

## 9.1 Freeze 狀態

| 元件 | 狀態 |
| --- | --- |
| `scripts/kiro_acp_bridge.py`（Kiro ACP Bridge） | **Production Baseline / Frozen** |
| `scripts/codex_image_adapter.py`（Codex Image Adapter，含 Phase 5.1 ambiguity fix） | **Production Baseline / Frozen** |

Freeze 意義：除非出現實際 integration blocker / bug，否則後續 Phase 不得順手 refactor。

## 9.2 Source Grounding & Traceability（optional，source-driven 專案適用）

`scripts/source_grounding.py` 提供一組獨立於 `project_state.py` 的 sidecar
artifact（`source_inventory.json`、`claim_traceability.json`、
`source_coverage.json`、`source_grounded_qa.json`），供有 source document 的
專案（例如需要對照契約、報告等原始文件產出簡報）記錄 source unit、claim 對應、
coverage accounting 與最終 grounded QA report。

- **Optional capability**：純創意、無 source 的簡報完全不受影響，不需要建立
  任何這裡描述的 artifact。單一判斷方式：
  `source_grounding_enabled(workspace)`——只有 `source_inventory.json` 存在
  且 `enabled: true` 才算啟用。使用者只提供 logo／參考圖／風格樣張時
  **不算** factual source，不得因此啟用。
- **兩層分離**：AGY 負責 semantic judgement（source 切分、claim 對應、claim 是否
  被 source 支持、coverage priority 與 omission 理由、數字/模態語意、最終
  Content QA outcome）；Python validator 只負責 schema 形狀、ID 完整性、參照
  存在性、coverage accounting 與 unresolved-claim 偵測，**永遠不會自己判斷一個
  claim 是否為真**，也不做 OCR、不解析契約語意。
- **與既有 Visual QA 完全分離**：不改寫、不覆蓋 `generated -> qa_passed/qa_failed`
  的既有語意。Content QA（source grounding）與 Visual QA 是兩個獨立 gate。

### 9.2.1 Source-driven 分支（接在第 6 節正常流程之上）

當 `source_grounding_enabled(workspace)` 為 true 時，AGY 在既有流程中額外負責：

| 既有流程階段 | 額外的 source-grounding 動作 |
| --- | --- |
| 1（讀取來源資料） | 建立 `source_inventory.json`（`enabled: true`）、記錄 `source_digest`、把 source 切成 source units 並標 priority |
| 3（確認 `outline.md`） | 規劃每個 source unit 的 coverage 意圖（進 slide / 只進 speaker notes / 明確不放並附理由） |
| 9–10（逐頁產圖並收回結果） | 為每頁登錄 claims（`claim_id`、`source_unit_ids`） |
| 11（AGY 檢查文字、事實、版式…） | Content QA：為每個 claim 給出 `support_status`，記錄 numeric/modal evidence，完成 coverage accounting |
| 13（產生 `speech.md`） | 只進 speaker notes 的 source-dependent claim 也要有 claim 與 `speaker_notes_only` coverage |
| **14 之前（執行 `assemble_ppt.py` 前）** | **必須**先跑 deterministic gate：`python3 scripts/validate_source_grounding.py <workspace>`。exit code 非 0 時**不得**呼叫 `assemble_ppt.py`，改為修復 grounding/Content QA 後重新驗證 |
| 16（回報產物） | 產生／更新 `source_grounded_qa.json`，含 AGY 的 `agy_qa_outcome` |

Gate 失敗是 **grounding precondition failure，不是 assembly failure**
（`assemble_ppt.py` 根本沒被呼叫），不得記錄成 Phase 9 assembly recovery；
也不會讓專案進入 `blocked`——它是可恢復的 AGY workflow issue。

詳見 `docs/source-grounding.md`。Schema：`schemas/source_inventory.schema.json`、
`schemas/claim_traceability.schema.json`、`schemas/source_coverage.schema.json`、
`schemas/source_grounded_qa.schema.json`。

## 10. 必讀檔案

- `docs/architecture-and-design-rationale.md`
- `docs/agent-routing.md`
- `docs/oauth-subscription-runtime.md`
- `docs/codex-image-runtime.md`
- `docs/runtime-state-and-routing.md`
- `docs/workflow-gates-and-progress.md`
- `docs/outline-style-and-sample.md`
- `docs/slide-generation-and-subagents.md`
- `docs/project-assembly-and-reporting.md`
- `docs/source-grounding.md`（optional，僅適用於有 source document 的 source-driven 專案）
