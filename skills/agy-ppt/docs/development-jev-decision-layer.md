# Jev 開發決策層

> 狀態：**ACTIVE — DEVELOPMENT-TIME ONLY**  
> 適用範圍：v0.6.0 Presentation Quality Hardening 與後續 repository engineering  
> 不屬於產品 runtime、CI 或 release authority

Codex 是 repository 的 Engineering Lead / Development Orchestrator。Jev 是 Codex 底下的
**Bounded Engineering Decision Engine**。產品 runtime authority 完全不變：

`User → AGY → Codex production worker → agy-ppt → PPTX`

Jev 不得出現在此 runtime chain；AGY 仍是 sole product orchestrator / semantic authority。

## 1. 決策階層

1. **DETERMINISTIC**：固定規則能可靠回答時，由 deterministic code 直接判斷。
2. **JEV**：bounded、repeated、typed/classifiable、semantically non-trivial 且會影響 engineering branch
   的判斷，預設交給 Jev。
3. **CODEX REASONING**：open-ended architecture、causal debugging、證據不足、新型 failure、Jev 結果
   衝突或 confidence 不足時，由 Codex 完整推理。

Jev 不重複回答已經固化成 deterministic rule 的問題。採用的判斷必須轉成 repository-owned code、
tests、fixtures、typed enums、compatibility matrix、regression expectation 或 documented contract。

## 2. Confidence 與 escalation

- `>= 0.85`：`HIGH_CONFIDENCE`；僅在與 deterministic evidence 一致時可採用。
- `0.65–0.84`：`REVIEW_REQUIRED`；Codex review 後才可分支實作。
- `< 0.65`：`ESCALATE`；Codex 執行完整 engineering reasoning。
- choice probability 前兩名差距小於 `0.15`，或結果互相矛盾：不論 nominal confidence，皆
  `ESCALATE`。

此 routing 已由 `dev_jev_decisions.py` 與 offline tests 固化。Jev service unavailable 時直接降級為
Codex reasoning；不得阻擋 runtime、CI 或 release validation。

## 3. Decision record

Meaningful Jev-assisted decision 必須留下 sanitized lightweight record，包含：

- `decision_id`
- task / question
- bounded answer schema
- evidence / fixture references
- Jev result 與 confidence
- Codex action
- escalated yes/no
- final engineering disposition
- repository capture（code/test/fixture/doc）

不得保存 API key、authorization header、credential、private input 或未清理的 live transcript。

## 4. Q1 — Live Worker Contract Wiring 實驗紀錄

2026-09-23 使用 repository-owned synthetic fixtures，透過 TypeSafe `jev-latest` 執行 9 個
independent Choice judgments。輸入未含 confidential material 或 credential；完整 raw service response
不進 repository。

| Decision ID | Schema / fixture | Jev result | Confidence | Codex disposition | Repository capture |
|---|---|---:|---:|---|---|
| Q1-JEV-001 | `COMPLETE/PARTIAL/UNSAFE` — complete worker job | COMPLETE | 0.99 | 採用；要求完整 manifest | `audit_worker_contract` + tests |
| Q1-JEV-002 | 同上 — contradictory native overlay job | UNSAFE | 0.94 | 採用；dispatch 前 fail closed | adapter parser + tests |
| Q1-JEV-003 | `CLEARLY_PROPAGATED/AMBIGUOUS/MISSING` — vague empty-area prompt | AMBIGUOUS | 0.96 | 採用；不接受含糊 exclusion | canonical prompt renderer + tests |
| Q1-JEV-004 | 同上 — explicit zone/exclusion/failure prompt | CLEARLY_PROPAGATED | 1.00 | 採用；固化 prompt tokens/manifest hash | prompt compliance rule + tests |
| Q1-JEV-005 | `LIVE_VERIFIED/PROXY_ONLY/INSUFFICIENT_EVIDENCE` — complete live record | LIVE_VERIFIED | 1.00 | 採用；要求 dispatch/job/thread/result/artifact identities | qualification classifier + tests |
| Q1-JEV-006 | 同上 — callback record | PROXY_ONLY | 1.00 | 採用；proxy 永不冒充 live | qualification classifier + tests |
| Q1-JEV-007 | 同上 — thread-only record | INSUFFICIENT_EVIDENCE | 1.00 | 採用；證據不足不得宣稱 live | qualification classifier + tests |
| Q1-JEV-008 | `RAW_PLATE/HYBRID_PREVIEW/AMBIGUOUS` — plate artifact | RAW_PLATE | 1.00 | 採用；raw plate 不得成為 sample fidelity 證明 | sample provenance + tests |
| Q1-JEV-009 | 同上 — manifest/render-hashed preview | HYBRID_PREVIEW | 1.00 | 採用；Hybrid Preview 必須顯式可證 | sample provenance + tests |

統計：9 fixtures；9 high-confidence；0 review-required；0 low-confidence/escalated；0 unresolved。
Jev 判斷均先由 Codex 與 deterministic evidence 交叉檢查後才採用。

## 5. 權限與禁止事項

Jev 可以協助 bounded development classification，但不得決定：PR merge、CI pass、tag/release、
human presentation quality、evidence factual truth 或產品語意。`HUMAN_PRESENTATION_QUALITY` 仍只能由
human acceptance 通過；human rejection 一律覆蓋任何 automated classification。

Repository runtime 與 CI 對 Jev 的 dependency 為 **NONE**。TypeSafe credential 只存在於開發環境，
不得 commit。
