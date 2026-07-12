---
type: goal-plan
schema_version: 1
goal_id: database-migration-preflight
status: draft
updated: 2026-07-11
contract: artifacts/database-migration-preflight/CONTRACT.md
evidence: artifacts/database-migration-preflight/EVIDENCE.md
---

## Execution Plan

1. 指定 owner、資料庫引擎／版本、來源與目標環境、遷移腳本版本及受影響服務。
2. 確認資料分類、合規限制、可接受停機、RPO/RTO、容量與鎖定風險；補齊範圍與非目標。
3. 在隔離或 staging 環境演練遷移，記錄資料與效能基準、相容性測試及失敗情境。
4. 建立並驗證備份；演練 restore 與 rollback／forward-fix，記錄決策門檻與責任人。
5. 取得必要審查 `PASS` 後，才排定 production rollout；以分階段方式執行並監控已核准指標。
6. 執行後完成資料比對、服務健康檢查與觀察期；將最終結果寫入 EVIDENCE，再決定完成或恢復。

## Verification Plan

- 結構驗證：預期 schema、索引、約束、權限與版本皆符合。
- 資料驗證：已定義的筆數、校驗、抽樣與業務不變量均通過。
- 服務驗證：讀寫路徑、背景工作、依賴服務、延遲與錯誤率在核准門檻內。
- Recovery 驗證：restore／rollback 或 forward-fix 在測試環境成功，且預估時間符合 RTO。

## Rollback Runbook Skeleton

1. 停止 rollout，凍結寫入或啟用已核准的降級模式。
2. 通知責任人與值班窗口，保存診斷與監控證據。
3. 依已演練版本回退應用程式與可逆 schema；若不可逆，從已驗證備份 restore 或執行核准的 forward-fix。
4. 重跑資料、schema 與服務健康驗證；確認一致性後才解除限制。
5. 記錄事件、實際 RPO/RTO、殘餘風險及下一步審查。

## Progress Log

- 2026-07-11：建立 preflight 草稿；等待目標、範圍與 owner 資訊。未執行任何遷移。
