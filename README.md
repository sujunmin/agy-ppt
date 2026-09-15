# agy-ppt

**沒有 AI 味的報告。**

內容有根據，呈現像人做的。

**語言：** 繁體中文 | [English](README_en.md)

`agy-ppt` 把文章、報告與來源文件轉成圖片式 PowerPoint。AGY 負責大綱、設計方向、內容與品質；專用 worker 產生單頁圖片，最後組裝成含講稿的 `.pptx`。

## 安裝

需求：Python 3.11+、Git，以及已登入並可使用圖片生成工具的 agent 環境。

```bash
git clone https://github.com/sujunmin/agy-ppt.git
cd agy-ppt
python3 skills/agy-ppt/scripts/codex_ppt_runtime.py bootstrap
mkdir -p ~/.gemini/config/skills
rsync -a --delete ./skills/agy-ppt/ ~/.gemini/config/skills/agy-ppt/
```

`bootstrap` 只建立共用 runtime 並安裝執行所需依賴；它不會執行測試、OCR qualification 或產生範例簡報。其他 agent 可把 `skills/agy-ppt/` 放到其支援的 workspace skill 位置。

## 基本使用

載入 `agy-ppt` skill 後，向 AGY 說明主題、受眾、頁數與來源，例如：

```text
請把這份報告做成 10 頁的繁體中文簡報，對象是部門主管。
```

預設互動流程會逐步請你確認：

1. 確認大綱
2. 確認視覺風格
3. 檢視一張真實樣張
4. 核准後產生完整簡報

修改大綱或風格會使相依的樣張核准失效；在三個核准完成前，不會產生整套簡報。

## 運作方式

```text
使用者需求 / 來源
  → 大綱核准
  → 風格核准
  → 單張樣張核准
  → 完整簡報
```

含 OCR 的來源會先建立可追溯證據，再交回 AGY 判斷：

```text
PDF / 圖片 → 擷取 / OCR 證據 → 來源接地 → AGY
```

AGY 始終是唯一的 orchestrator 與語意判斷者；OCR 與圖片 worker 不會自行改寫內容或跳過核准階段。

## 支援的輸入

- Markdown、純文字、DOCX、靜態 HTML 與既有來源系統支援的公開遠端內容
- 可搜尋、掃描及混合型 PDF
- PNG、JPEG、單幀 TIFF

多幀 TIFF 會被明確拒絕。OCR 準確度取決於來源品質、provider 與模型。

## 文件

- [簡報核准流程](skills/agy-ppt/docs/outline-style-and-sample.md)
- [Phase 16：有根據的簡報規劃與人類編輯品質](skills/agy-ppt/docs/phase16-grounded-presentation-and-editorial-quality.md)
- [架構與角色分工](skills/agy-ppt/docs/architecture-and-design-rationale.md)
- [來源取得、擷取與接地](skills/agy-ppt/docs/source-ingestion.md)
- [OCR 架構與 providers](skills/agy-ppt/docs/phase15-ocr-architecture.md)
- [安全、CI 與開發測試](skills/agy-ppt/docs/ci-quality-gates.md)
- [故障恢復](skills/agy-ppt/docs/recovery-testing.md)
- [變更紀錄](CHANGELOG.md)

開發者的完整測試與 release qualification 指令位於上述 CI／測試文件，不屬於一般使用者安裝流程。

## 專案狀態與授權

Phase 15 OCR 與來源接地管線已完成並凍結；Phase 16 架構已定義但尚未開始實作。Linux x86_64 是主要 production target，但正式部署仍需驗證 hard isolation；macOS 僅供開發/API 驗證，Windows 尚未通過 production-security qualification。OCR JSON schemas 仍為 deferred。

本專案採 [MIT License](LICENSE)，衍生自 [`ningzimu/codex-ppt-skill`](https://github.com/ningzimu/codex-ppt-skill)，並非 upstream 官方版本。第三方授權資料見 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
