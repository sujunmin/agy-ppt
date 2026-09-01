# Workflow Gates 與進度控制

## Gate 1：需求與輸入

確認：

- source material
- audience
- goal
- page count
- required assets
- forbidden changes

## Gate 2：大綱

AGY 建立 `outline.md`。

原則：
- 文字內容完整性優先，**不設定固定字數上限**。不得單純因字數多而強制拆頁、刪字或縮寫。
- 若特定頁面資訊量較大，在規劃階段即應預先考量雙欄、2×2、2×3、卡片矩陣、流程或 Checklist 等結構化版型。
- 如果使用者要求先確認，未確認前不要大規模生圖。

## Gate 3：視覺方向

AGY 定義 style system。

## Gate 4：圖片 backend 可用性

確認 Codex `$imagegen` / built-in `image_gen` 可用。

不可用時：

```text
IMAGE_BACKEND_UNAVAILABLE
```

## Gate 5：樣張

生成代表性樣張，AGY QA。

## Gate 6：批次生成

AGY 建立全部 jobs，逐頁派 Codex。

## Gate 7：整套 QA（Visual QA）

檢查：

- **文字正確性**：逐字核對權威文案（authoritative text），繁體字形正確無錯字、無漏字、無多字、無簡體字、無亂碼。
- **排版與可讀性**：字級清楚可讀、無裁切、無重疊、長句換行合理、保留足夠留白。
- **文字密度判定原則**：
  - 不以硬性字數門檻（如 240 / 300 字）判定失敗；Phase 8A 已實證系統至少可穩定處理約 79～239 字／頁（已驗證成功範圍）。
  - 只要文字精確、排版清楚、閱讀動線舒適，即可判定 `qa_passed`。不得僅因「文字很多」判失敗。
- **Regenerate 優先於拆頁**：若排版太擠或間距不佳，先由 AGY 判定 `qa_failed -> ready -> regenerate` 要求 Codex 調整版型。僅在單頁確定無法清晰容納時才允許拆頁。
- **資料完整性與風格**：事實無誤、required assets 完整保留、整份簡報風格嚴格一致。


## Gate 8：組裝

執行既有 assembly script。

## 工程插入點

任何 gate 遇到「需要修改 executable code」：

```text
目前 phase 暫停
 -> AGY 建立 engineering task
 -> Kiro
 -> 回 AGY
 -> 驗收後恢復原 phase
```
