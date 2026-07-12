---
type: goal-plan
schema_version: 1
goal_id: login-retry
status: draft
updated: 2026-07-11
contract: artifacts/login-retry/CONTRACT.md
evidence: artifacts/login-retry/EVIDENCE.md
---

## Execution Plan

1. 確認登入架構、目前的速率限制/鎖定/MFA/session 控制，以及受影響的 UI 與 API 合約。
2. 與產品、認證與安全負責人核准可重試錯誤、最大次數、退避、取消、文案與遙測最小欄位。
3. 先寫或更新失敗測試，覆蓋暫時性失敗、不可重試失敗、上限、取消與防護控制。
4. 以不繞過服務端控制的方式實作重試；避免重複送出、重複 session 與競態。
5. 加入已審核的最小化診斷資料與操作文件。
6. 執行測試、進行安全審查、將結果與殘餘風險填入 `EVIDENCE.md`。

## Verification Plan

- 單元測試：分類、上限、退避、取消與 UI 狀態。
- 整合測試：登入 API、速率限制、帳號鎖定、MFA、session 唯一性與錯誤遮蔽。
- 端對端測試：使用者可重試的暫時性失敗及不可重試失敗的明確處理。
- 安全檢查：無敏感日誌、無帳號枚舉資訊、無防護控制繞過。

## Rollback And Recovery

使用可關閉的功能旗標或等效既有設定（若系統具備）停用新重試路徑，保留既有單次登入流程。若無此機制，部署前必須記錄可回復到前一已驗證版本的程序。不得以回滾為由刪除安全審計資料。

## Progress Log

- 2026-07-11：建立交接契約；尚未開始程式碼或設定變更。

## Open Decisions

- 目標平台、受影響模組與登入協定。
- 可重試錯誤碼、重試次數、退避公式與使用者可見文案。
- 遙測保留期、告警門檻與安全審查負責人。
