---
type: goal-plan
schema_version: 1
goal_id: global-goal-preflight-edit
status: blocked
updated: 2026-07-11
contract: artifacts/global-goal-preflight-edit/CONTRACT.md
evidence: artifacts/global-goal-preflight-edit/EVIDENCE.md
---

## Execution Plan

1. 釐清所需的具體 Skill 行為變更及其接受標準。
2. 識別唯一受影響的全域 Skill 檔案，提出最小化 patch 與備份／rollback。
3. 取得獨立審查並記錄 verdict。
4. 僅在 verdict 為 `PASS` 且具備明確授權時套用變更。
5. 驗證觸發、非觸發與 reviewer gate 行為，將結果記入證據檔。

## Verification Plan

驗證變更不會擴及其他全域設定或 Skill，並覆蓋明確 preflight 請求、一般工作請求與全域 Skill 變更的審查門檻。

## Rollback

套用前的已驗證備份為唯一 rollback 來源；若驗證失敗，還原該備份並重新檢查行為。

## Progress Log

- 2026-07-11：已建立隔離評估用契約；因缺少具體行為規格與必要獨立審查而阻塞。

## Open Decisions

- 使用者希望改變的精確行為為何？
- 哪一位獨立 reviewer 可提供 `PASS`、`FAIL` 或 `NEEDS_EVIDENCE` verdict？
