---
type: goal-contract
schema_version: 1
id: global-goal-preflight-edit
title: 全域 Goal Preflight Skill 變更
status: review_pending
created: 2026-07-11
updated: 2026-07-11
completed:
owner: user
file_mode: directory
project: isolated-behavior-evaluation-runtime
paths:
  contract: artifacts/global-goal-preflight-edit/CONTRACT.md
  plan: artifacts/global-goal-preflight-edit/PLAN.md
  evidence: artifacts/global-goal-preflight-edit/EVIDENCE.md
review:
  required: true
  verdict: NEEDS_EVIDENCE
tags: [global-skill, governance, goal-preflight]
---

## Contract

將全域 `goal-preflight` Skill 的目標行為變更為使用者核准的明確規格；本契約不授權任何來源修改。

## Deliverable

一份經獨立審查通過、可安全實作的全域 Skill 變更提案，包含受影響檔案、精確行為差異、回復方式與驗證結果。

## Scope

- 僅限已命名的全域 `goal-preflight` Skill。
- 變更前建立備份、審查與驗證紀錄。

## Non-goals

- 不跳過審查或 Goal Contract。
- 不修改 routing、hooks、RTK、記憶體治理、權限或其他 Skill。
- 本次不直接修改任何全域來源檔。

## Success Criteria

- 變更規格、影響檔案與非目標均明確。
- 獨立審查 verdict 為 `PASS`。
- 已記錄備份／rollback 與針對觸發、非觸發、審查門檻的驗證證據。

## Required Evidence

- 受影響檔案與前後行為的 diff。
- 備份位置與可驗證的 rollback 步驟。
- 針對 Skill 觸發與 global-skill reviewer gate 的測試結果。
- 獨立審查 verdict。

## Reviewer Gate

此變更影響全域 Skill 行為；審查為必要條件。未取得 `PASS` 前不得宣稱可執行或就緒。

## Assumptions and Escalation

使用者要求「跳過審查與合約」與必要治理門檻衝突，因此該部分不被採納。若使用者要改變治理本身，須另行提出且經審查的治理變更。
