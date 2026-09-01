# agy-ppt

以 AGY 為唯一 orchestrator / state owner，Kiro V3 `ppt-engineer` 為專職 engineering
worker，Codex CLI 為專職 slide-image worker 的圖片式 PPT/PPTX 生成工作流程。

> 本專案是 [`ningzimu/codex-ppt-skill`](https://github.com/ningzimu/codex-ppt-skill)
> 的衍生作品（derivative work），並非 upstream 官方版本，也未獲得 upstream 作者背書。
> 詳見下方 [Upstream & Attribution](#upstream--attribution)。

## Standalone Repository

`agy-ppt` is a standalone repository.

本專案不包含（vendor）完整 upstream `codex-ppt-skill` checkout，也沒有把它做成
Git submodule。`codex-ppt` 是一個 **external runtime dependency**：只有在真的需要
upstream 未經修改的原始實作時，才由
[`skills/agy-ppt/scripts/codex_ppt_dependency.py`](skills/agy-ppt/scripts/codex_ppt_dependency.py)
在需要的當下解析／下載，快取在本 repository 之外的位置。詳見下方
[codex-ppt Dependency](#codex-ppt-dependency)。

## 一句話用途

把文章、報告、大綱等內容規劃成大綱與視覺風格後，逐頁生成整頁圖片式投影片，
交由 AGY 驗收，最後組裝成 `.pptx`；過程中的 state、resume、故障恢復皆為
deterministic 且可稽核。

## Architecture

```text
AGY -> worker -> AGY
```

這是唯一允許的 routing。三個角色分工明確、互不越權：

| 角色 | 職責 |
| --- | --- |
| **AGY** | 唯一 orchestrator / state owner。決定大綱、頁數、故事線、視覺策略、文案、approval gates、content QA / visual QA、是否重生圖片、是否進入組裝與完成階段。 |
| **Kiro V3 `ppt-engineer`** | Engineering worker only。只負責寫程式、改程式、debug、tests、schema/tool contract、CLI/ACP adapter、dependency/build、filesystem automation、PPTX assembly tooling。不得修改簡報內容、已核准文案、頁數、視覺策略或 slide image。 |
| **Codex CLI** | Slide-image worker only。只負責生成或編修一張整頁投影片圖片，並回傳結果。不得改文案、改頁數、寫程式、組裝 PPTX 或自行切換 image backend。 |

嚴格禁止以下 routing（worker 之間不得互相呼叫或轉交流程）：

```text
AGY -> Kiro -> Codex   (禁止)
AGY -> Codex -> Kiro   (禁止)
Kiro -> Codex          (禁止)
Codex -> Kiro          (禁止)
```

worker 完成後一律把結果交回 AGY，由 AGY 決定下一步；worker 不持有簡報 context、
不做下一步決策。完整說明見
[`skills/agy-ppt/docs/agent-routing.md`](skills/agy-ppt/docs/agent-routing.md)
與
[`skills/agy-ppt/docs/architecture-and-design-rationale.md`](skills/agy-ppt/docs/architecture-and-design-rationale.md)。

## Key Features

- **AGY-owned deterministic project state**（`scripts/project_state.py`）：deck 級
  phase state machine、每頁 slide state machine、generation 計數器、attempt
  歷史、resume/recovery、worker-result 驗證，皆為 AGY-only 寫入。
- **Codex 訂閱 session 生圖**（`scripts/codex_image_adapter.py`）：透過已登入的
  Codex CLI 訂閱 session 呼叫內建 `image_gen`，不使用 API key，不自動 fallback
  付費 API。
- **Kiro V3 ACP bridge**（`scripts/kiro_acp_bridge.py`）：把工程需求（寫程式、debug、
  測試）交給 Kiro V3 `ppt-engineer`，agent scope 為整個 turn 的 runtime invariant，
  一旦漂移即中止並回報，不猜成功。
- **最多一次 immediate retry 的故障政策**：同一頁連續兩次相同的
  `IMAGE_GENERATION_FAILED` 即 block 專案，不會無限重試；operator 可另外明確記錄
  「額度已耗盡」的決策，但不會偽造成 worker error code。
- **Deterministic fault-injection 測試套件**（`skills/agy-ppt/tests/recovery/`）：
  涵蓋 generation failure、backend unavailable、ambiguous artifact、invalid
  output、interrupted generation、QA regeneration、assembly failure、resume
  idempotency 等情境，不消耗任何 AI 訂閱額度。
- **External codex-ppt dependency resolver**（`scripts/codex_ppt_dependency.py`）：
  單一 dependency-resolver authority，deterministic 地把「latest」定義為 upstream
  `main` 分支的目前 HEAD，具備 offline 重用快取、atomic cache update 與明確的
  dependency-unavailable 失敗語意。詳見
  [`skills/agy-ppt/docs/upstream-differences.md`](skills/agy-ppt/docs/upstream-differences.md)。

## OAuth / Subscription Runtime

預設 profile 是「訂閱登入優先、零 API key」：

```text
AGY   = Google AI Pro 登入 session（Antigravity / Gemini CLI）
Kiro  = Kiro Pro 登入 session（Kiro CLI V3）
Codex = ChatGPT Plus / Codex 登入 session
```

各 CLI 自行管理自己的 credential；本專案的程式碼不讀取、不複製、不轉傳任何
OAuth access token / refresh token。詳見
[`skills/agy-ppt/docs/oauth-subscription-runtime.md`](skills/agy-ppt/docs/oauth-subscription-runtime.md)。

## No Production API-Key Fallback

正式 workflow 預設關閉 API-key 路徑：

- `codex_image_adapter.py` 會在呼叫 Codex CLI 前，從子行程環境變數中移除
  `OPENAI_API_KEY` 等 API-key 類變數，只記錄變數**名稱**，絕不記錄數值。
- 若 Codex 目前 session 沒有暴露內建 `image_gen`，回報 `IMAGE_BACKEND_UNAVAILABLE`
  並把控制權交回 AGY，**不會**自動切換到付費 API。
- 衍生自 upstream 並改作的 `scripts/image_gen.py` 與 `scripts/image_providers/`
  （API-key/第三方供應商路徑）位於 `skills/agy-ppt/scripts/`，僅供需要此路徑的
  使用者自行選用；正式 workflow 的預設路徑不會自動觸發它。

詳見
[`skills/agy-ppt/docs/cli-api-fallback.md`](skills/agy-ppt/docs/cli-api-fallback.md)。

## codex-ppt Dependency

`codex-ppt` is not bundled or vendored in this repository.

- **First use**：當某個功能第一次真的需要 upstream 未修改的原始實作時，
  `resolve_codex_ppt_dependency()` 會建立一個 external dependency cache
  directory（OS 應用程式快取位置，不在本 repository、不在 Global AGY Skill 安裝
  位置、也不在任何簡報 workspace 之內），用 shallow clone 從固定 upstream URL
  （`https://github.com/ningzimu/codex-ppt-skill.git`）取得 `main` 分支，驗證
  checkout 內容後，回傳解析後的 dependency root。
- **Update**：之後再次需要時，resolver 會依 dependency resolver policy 檢查／解析
  upstream 目前最新版本（`main` 分支的 HEAD commit）；如果 upstream 沒有變化就直接
  重用既有快取，如果已更新則透過「temporary checkout → 驗證 → atomic replace」的
  方式更新快取，確保更新失敗時不會破壞既有可用的快取。
- **Offline**：如果暫時無法連線到 upstream，且本機已有快取，會重用既有快取並印出
  清楚的 warning（附上目前使用的快取 commit SHA）；這不是 API fallback。如果沒有
  快取又無法連線，會得到明確、deterministic 的
  `CODEX_PPT_DEPENDENCY_UNAVAILABLE` 錯誤，這是 dependency/bootstrap 失敗，
  與 Phase 10.3 的 `IMAGE_GENERATION_FAILED` worker retry 語意完全分離，不會混用。
- **Authentication**：解析 public GitHub 上的 upstream 只使用一般、未經身份驗證的
  `git` 操作；不需要、也不會讀取 `OPENAI_API_KEY`、`CODEX_API_KEY`、
  `KIRO_API_KEY`、`GEMINI_API_KEY`，或任何 AGY/Kiro/Codex 的 OAuth session。
- **Local override（選用）**：開發或離線測試時，可以設定
  `AGY_PPT_CODEX_PPT_HOME=/path/to/codex-ppt` 明確指定一個本機既有的 codex-ppt
  checkout；resolver 會直接使用該路徑，不會複製內容進本 repository，也不會把這個
  路徑寫進 Project State。

詳見
[`skills/agy-ppt/scripts/codex_ppt_dependency.py`](skills/agy-ppt/scripts/codex_ppt_dependency.py)
的模組文件字串，內含完整的 resolver 設計與失敗語意說明。

## Installation

### 全域安裝 AGY Skill

AGY skill（`skills/agy-ppt/`）可安裝於：

```text
~/.gemini/config/skills/agy-ppt/
```

或安裝到你正在使用的專案 workspace：

```text
/path/to/agy-ppt/.agents/skills/agy-ppt/
```

本地開發時建議用符號連結，方便即時測試：

```bash
mkdir -p ~/.gemini/config/skills
ln -s /path/to/agy-ppt/skills/agy-ppt ~/.gemini/config/skills/agy-ppt
```

### Kiro `ppt-engineer` 設定

`ppt-engineer` 是 Kiro 端的專用 custom agent，定義檔放在：

```text
<repo>/.kiro/agents/ppt-engineer.md
```

唯一受支援的 runtime 是 **Kiro CLI V3**，正式啟動方式：

```bash
kiro-cli --v3 acp --auth-method cli
```

V2 引擎不受支援，`kiro_acp_bridge.py` 會拒絕並回報 `UNSUPPORTED_KIRO_ENGINE`。
`--auth-method cli` 讓 kiro-cli 自行解析既有登入 session；省略此參數會要求 ACP
client 代為提供 token，這是本專案禁止的行為。

### Codex CLI 需求

- 需要已登入的 Codex CLI（ChatGPT Plus / Codex 訂閱 session），且當前 session
  能暴露內建 `image_gen` 工具（`$imagegen` skill）。
- 標準呼叫方式：`codex exec --json --skip-git-repo-check`，prompt 透過 stdin 傳入。
- 不需要 `OPENAI_API_KEY` 或任何第三方生圖 API key。

## Quick Start

1. 安裝並登入三個 CLI（AGY / Kiro / Codex），確認各自的訂閱 session 可用。
2. 在你的 agent 環境中載入 `skills/agy-ppt/SKILL.md`。
3. 對 AGY 描述你要做的簡報，例如：

   ```text
   請幫我把 /path/to/article.md 做成 10 頁左右的 PPT。
   ```

4. AGY 會依序引導確認大綱、視覺風格、樣張，再逐頁生成、驗收、組裝成 `.pptx`。

## External Project Workspace

每個 PPT 專案會有自己獨立的 workspace 目錄，與本 repository 的原始碼分離，例如：

```text
~/projects/my-presentation/
├── origin_image/           # 正式幻燈片圖片，只放最終採用的頁面
│   ├── slide_01.png
│   └── ...
├── prompts/                 # 每頁的完整生圖 prompt
├── outline.md                # 已確認的大綱
├── speech.md                  # 演講稿，會寫入 PPT 每頁備注
├── project_state.json          # AGY-owned deterministic project state
└── my-presentation.pptx        # 最終組裝產物
```

`project_state.json` 是 AGY 專用的 deterministic state 檔，由
`scripts/project_state.py` / `scripts/validate_project.py` 操作，永遠不應該被提交
到本原始碼 repository。

## State / Resume / Recovery

`project_state.json` 記錄：

- deck phase state machine：`intake -> outline -> style -> sample ->
  slide_generation -> visual_qa -> assembly -> complete`，任何 phase 可
  `-> blocked`。
- slide state machine：`planned -> ready -> generating -> generated ->
  qa_passed/qa_failed -> assembled`，`generation_failed` 可退回 `ready` 重生。
- 每頁的 `generation` 計數器與完整 `attempts` 歷史（不會被覆寫或消失）。

Resume 行為：

- 已 `qa_passed` / `assembled` 的頁面不會被重新生成（image bytes 不變）。
- 從磁碟重新載入 state 的全新 process，只會派發尚未完成的頁面。
- 中斷在 `generating` 的頁面，只有在同時具備「completed 的 worker result」與
  「已驗證存在的 artifact」時才會被判定為 `generated`；否則一律判定為
  `generation_failed`，絕不猜測成功。
- 同一頁連續兩次相同的 `IMAGE_GENERATION_FAILED` 會讓專案 `phase -> blocked`
  （並記住 `phase_before_block`），需要 AGY 明確 resume 才會繼續。

詳見
[`skills/agy-ppt/docs/runtime-state-and-routing.md`](skills/agy-ppt/docs/runtime-state-and-routing.md)
與
[`skills/agy-ppt/docs/recovery-testing.md`](skills/agy-ppt/docs/recovery-testing.md)。

## Testing

一般 unit tests **不會**消耗任何 AI 訂閱額度、不呼叫真實 Codex/Kiro，全部使用
deterministic fake worker：

```bash
python3 -m unittest discover -s skills/agy-ppt/tests -t skills/agy-ppt/tests -p "test_*.py"
python3 skills/agy-ppt/scripts/run_recovery_tests.py
```

Live 測試需要明確 opt-in 才會執行，且會消耗真實訂閱額度，請不要無必要地執行：

```bash
# 呼叫真實 Codex 生成一張圖片做端到端驗證
AGY_PPT_LIVE_CODEX_IMAGE=1 python3 skills/agy-ppt/tests/integration/test_codex_imagegen_live.py

# Phase 9 live failure & recovery（partial resume / regenerate / assembly recovery）
AGY_PPT_LIVE_RECOVERY=1 python3 skills/agy-ppt/scripts/run_live_recovery_tests.py

# 額外執行 process-interruption 情境（會終止一個由測試自己建立並追蹤的 Codex process）
AGY_PPT_LIVE_RECOVERY=1 AGY_PPT_LIVE_RECOVERY_INTERRUPT=1 \
    python3 skills/agy-ppt/scripts/run_live_recovery_tests.py
```

詳見
[`skills/agy-ppt/docs/recovery-testing.md`](skills/agy-ppt/docs/recovery-testing.md)。

## Limitations

- 第一版是 `sequential_only`：一次只生成一頁，故意不支援平行生成。
- 需要三個 CLI 各自登入對應的訂閱帳號；本專案不提供、不管理任何帳號或 credential。
- Codex 內建生圖工具目前解析度較低且不可手動指定；若需要更高解析度，需自行改用
  本專案保留的 API-key 路徑（`skills/agy-ppt/scripts/image_gen.py`），此路徑預設
  不會自動觸發。
- 生成的投影片是整頁圖片，頁面內的文字、圖形、版式本身不可個別編輯；如需可編輯
  PPT，可另外使用 upstream 作者的
  [`image-to-editable-ppt-skill`](https://github.com/ningzimu/image-to-editable-ppt-skill)
  轉換。
- Quota exhaustion 目前無法從 Codex CLI 的 subprocess evidence（returncode /
  stderr）deterministic 判斷；只有出現明確的機器可辨識 usage/quota/rate-limit
  訊號時才會新增專門的錯誤分類，操作人員可以另外用 operator-confirmed 的方式記錄
  額度耗盡，但不會偽造成 worker error code。

## Upstream & Attribution

本專案衍生自
[`ningzimu/codex-ppt-skill`](https://github.com/ningzimu/codex-ppt-skill)
（MIT License，`Copyright (c) 2026 ningzimu`）。本 repository 不包含完整 upstream
checkout；`skills/agy-ppt/` 內含衍生自 upstream 並改作的實作，而未修改的 upstream
原始實作則在真正需要時作為 external runtime dependency 解析，詳見上方
[codex-ppt Dependency](#codex-ppt-dependency)。

- 詳細差異比較：
  [`skills/agy-ppt/docs/upstream-differences.md`](skills/agy-ppt/docs/upstream-differences.md)
- 完整第三方來源與衍生/依賴內容清單：
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

**agy-ppt is not affiliated with or endorsed by the upstream author.**

## License

MIT License。詳見 [`LICENSE`](LICENSE)（同時保留 upstream 的
`Copyright (c) 2026 ningzimu` 與本專案新增部分的 copyright）。

## Acknowledgements

- 感謝 [`ningzimu/codex-ppt-skill`](https://github.com/ningzimu/codex-ppt-skill)
  提供成熟的圖片式 PPT 生成流程與風格庫作為基礎。
