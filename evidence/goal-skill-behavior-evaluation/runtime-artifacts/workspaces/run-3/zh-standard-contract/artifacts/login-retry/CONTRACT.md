---
type: goal-contract
schema_version: 1
id: login-retry
title: 登入重試功能
status: review_pending
created: 2026-07-11
updated: 2026-07-11
completed:
owner: identity-auth-engineering
file_mode: directory
project: current-project
paths:
  contract: artifacts/login-retry/CONTRACT.md
  plan: artifacts/login-retry/PLAN.md
  evidence: artifacts/login-retry/EVIDENCE.md
review:
  required: true
  verdict: NEEDS_EVIDENCE
tags:
  - authentication
  - retry
  - security
  - handoff
---

## Contract

### Goal

在既有登入流程中提供安全、可觀測且可測試的重試行為，讓暫時性失敗可由使用者再次嘗試，同時不削弱帳號防護或洩漏敏感資訊。

### Deliverable

完成可部署的登入重試實作，以及其測試、監測/日誌說明與交接證據；詳細執行與驗證紀錄分別維護於 `PLAN.md` 與 `EVIDENCE.md`。

### Scope

- 定義可重試與不可重試的登入失敗類型。
- 在登入 UI 與服務端邊界實作一致的重試限制、等待與錯誤呈現。
- 維持既有帳號鎖定、速率限制、MFA、session 與審計行為。
- 為成功、暫時性失敗、憑證錯誤、帳號鎖定、網路逾時及重試上限建立測試。
- 記錄不含密碼、token、完整個資的診斷事件與必要指標。

### Non-goals

- 不重設密碼、不變更帳號鎖定政策、不新增身份提供者。
- 不變更 MFA、session、授權範圍或使用者資料模型，除非後續另行核准。
- 不在本 Goal 中進行登入流程的整體視覺重設計。

### Success Criteria

- 暫時性、明確允許的失敗可依已核准策略重試；成功後只建立一個有效登入狀態。
- 錯誤憑證、帳號鎖定、挑戰失敗與政策拒絕不會被自動重試或被錯誤訊息區分為可枚舉的帳號狀態。
- 重試次數、退避規則與取消行為受設定限制，且不繞過既有速率限制或鎖定控制。
- 使用者可辨識目前狀態與下一步；錯誤內容不暴露敏感資訊。
- 單元、整合與必要的端對端測試通過，並有安全審查 `PASS` 後才可宣告可交付。

### Assumptions And Open Decisions

- 假設目標是現有產品的帳密登入流程，且可在前端與認證服務邊界修改；實際模組與平台待執行者確認。
- 重試上限、退避時間、可重試錯誤碼、UI 文案、遙測欄位與帳號鎖定互動尚未決定，必須在實作前由產品、認證與安全負責人核准。
- 預設不將原始認證錯誤或使用者識別資訊寫入日誌。

### Required Evidence

- 已核准的重試策略與風險清單。
- 覆蓋成功、失敗、逾時、取消、重試上限與帳號防護邊界的測試結果。
- 速率限制/鎖定/MFA/session 未被繞過的整合或端對端證據。
- 日誌與遙測欄位審查，證明未記錄密碼、token 或不必要個資。
- 安全審查 verdict：`PASS`。

### Reviewer Gate And Escalation

此變更觸及登入與帳號防護；安全審查為必要門檻。審查工具或授權未提供前，狀態維持 `review_pending`，不得宣告 ready 或完成。

若需修改帳號鎖定、速率限制、MFA、session、認證供應商、資料保留或正式環境設定，停止並取得明確的額外核准。

### Location And Activation

本契約依隔離評估環境限制寫於 `artifacts/login-retry/`，而非專案正式 `goals/active/`。它是供下一位執行者使用的暫存交接包；若要正式啟用，應由授權者移入目標專案的 `goals/active/login-retry/`，並在交接完成後依評估環境規則清理此副本。
