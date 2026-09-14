# 大綱、風格與樣張

預設互動式簡報流程必須依序通過三個使用者核准 gate：

```text
REQUEST
  -> OUTLINE_PENDING_APPROVAL
  -> STYLE_PENDING_APPROVAL
  -> SAMPLE_PENDING_APPROVAL
  -> FULL GENERATION
```

AGY 擁有流程與核准狀態；圖片 worker 只執行單頁 job，不能核准、跳過或推進 gate。

## 大綱

AGY 先建立 `outline.md`，至少包含：

- 簡報目的
- 受眾
- 頁數
- 每頁角色
- 每頁標題
- 核心訊息
- 必要資料／素材

AGY 此時只交付大綱供使用者確認。使用者要求修改時只更新規劃內容並再次請求核准；
不得先定稿風格、生成樣張或產生整套簡報。

## 視覺風格與文字密度

AGY 選擇一套統一 visual system，但不要求每頁使用完全相同 layout。

風格應涵蓋：

- 色彩
- 字型感
- 影像型別
- 留白密度
- 資訊密度與分區策略
- 圖表／卡片語言

只有已核准的大綱可以進入風格確認。AGY 以精簡、可判斷的方式呈現 visual direction、
typography、palette、density、影像處理與語氣，使用者核准後才可生成樣張。

### 文字密度與排版原則

- **不設定固定字數上限**：AGY 不得單純因字數多而強制拆頁、刪除文字或縮寫權威文案（authoritative text）。文字內容完整性優先。
- **已驗證範圍**：Phase 8A 實測已驗證目前系統至少能穩定處理約 79～239 字／頁的高密度繁體中文內容（此為已驗證成功範圍，而非系統限制）。更高文字量依實際 Visual QA 判斷。
- **高文字量優先調整版型**：若文字量較高，優先採用雙欄、2×2、2×3、多區塊卡片、比較矩陣、Checklist、流程圖、階梯或 Framework 分區佈局，避免預設使用易壅塞的單欄長條列。
- **Regenerate 優先於拆頁**：若排版過密或字級不佳，先透過 `regenerate` 要求 Codex 採用更合適之高密度版型；僅在確定單頁無論如何無法清晰容納時才允許拆頁。

## 樣張

在大量生圖前，先準備一個有代表性的 slide job，交給 Codex。預設穩定選擇大綱中
第一張非 cover/title 的內容頁；若沒有非封面頁則選第一頁。使用者可明確指定另一頁。

樣張用來驗證：

- 字是否可讀
- 資訊密度與版面佈局是否合理
- 視覺風格是否正確
- 圖文比例是否符合預期
- required asset 是否能被正確保留

樣張必須走實際單頁生成路徑，每次 sample attempt 只生成一張；不得先生成整套後只顯示
其中一張。最終是否接受樣張由 AGY／使用者決定，不由 Codex 決定。樣張生成失敗時
維持 `SAMPLE_PENDING_APPROVAL`，不得開始完整生成。

## 核准失效與恢復

- 大綱變更：`outline`、`style`、`sample` 的相依核准失效，從大綱重新確認。
- 風格變更：`style` 與 `sample` 核准失效，必須確認風格並重新生成一張樣張。
- 樣張變更：`sample` 維持未核准，直到修訂後的單張樣張再次通過。
- 完整生成失敗：保留仍屬目前 revision 的核准；只有失敗顯示規劃必須變更時才使相依 gate 失效。

`project_state.json` 的 gate metadata 保存 outline/style revision fingerprint 與樣張相依
revision。恢復 session 時只有與目前 deck plan 相符的核准可以重用，其他 deck 或舊 revision
的核准一律無效。完整生成的必要條件是：

```text
outline_approved == true
AND style_approved == true
AND sample_approved == true
```

完整簡報沿用已核准樣張的 typography、palette、spacing、visual language、image treatment
與元件樣式；每頁可以採用不同結構，但不得在核准後無聲改換整套設計方向。
