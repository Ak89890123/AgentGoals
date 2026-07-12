---
type: goal-contract
schema_version: 1
id: database-migration-preflight
title: 資料庫遷移前置範圍、驗收與回復契約
status: review_pending
created: 2026-07-11
updated: 2026-07-11
completed:
owner: tbd
file_mode: directory
project: isolated-behavior-evaluation
paths:
  contract: artifacts/database-migration-preflight/CONTRACT.md
  plan: artifacts/database-migration-preflight/PLAN.md
  evidence: artifacts/database-migration-preflight/EVIDENCE.md
review:
  required: true
  verdict: NEEDS_EVIDENCE
tags: [database, migration, rollback, preflight]
---

## Contract

在執行任何資料庫遷移前，確認遷移目標、受影響資料與系統、驗收條件，以及已測試的 rollback 流程；將可由後續執行者持續更新的決策、計畫與證據保留在本目錄。

## Deliverable

- 已核准的遷移範圍、非目標、相容性限制與停機／雙寫策略。
- 可量測的驗收條件與執行前、執行中、執行後證據。
- 已演練且具明確觸發條件的 rollback／recovery runbook。

## Scope

- 盤點 schema、資料轉換、索引、權限、依賴服務、讀寫客戶端與資料保留影響。
- 定義 staging／production 前置檢查、備份與還原驗證、資料正確性比對、效能與可用性監控。
- 定義分階段 rollout、停止條件、責任人與溝通窗口。

## Non-goals

- 未經明確核准，不執行遷移、備份、刪除、資料修復或任何 production 變更。
- 不以本文件取代資料庫平台既有的變更管理、存取控制或事故程序。

## Acceptance Criteria

- 遷移目標資料庫、版本、物件、資料量、依賴系統與排除範圍已具名記錄並經 owner 確認。
- 遷移腳本具可重複執行性或明確的一次性保護；前置條件、順序與預估時間已在非 production 環境驗證。
- 備份完整性、還原程序與資料正確性比對已在對等測試環境成功演練，且可接受的資料遺失／恢復時間目標已核准。
- rollout 監控指標、成功門檻、停止門檻、rollback 觸發者與通知名單已記錄。
- 獨立審查者以 `PASS` 確認計畫與證據；在此之前，本契約維持 `review_pending`。

## Rollback and Recovery

- Rollback 必須指定可安全回退的 schema／應用程式版本、資料回復來源、執行順序、預估耗時與資料遺失風險。
- 若偵測到資料一致性失敗、關鍵錯誤率／延遲超過已核准門檻、備份或驗證失敗，立即停止後續階段並依 PLAN 的 runbook 回復。
- 若遷移不可逆，必須明確標為不可逆，改以 restore／forward-fix 策略與加強核准取代「rollback」宣稱。

## Required Evidence

- 已核准的範圍與變更清單、資料分類與風險評估。
- staging 演練紀錄：腳本版本、開始／結束時間、驗證查詢結果、效能觀測與問題處置。
- 備份與還原演練紀錄，以及遷移前後資料完整性／筆數／校驗比對。
- rollback 或 recovery 演練紀錄、監控儀表板連結與獨立審查 verdict。

## Assumptions and Open Decisions

- 資料庫引擎、環境、遷移內容、資料敏感度、停機容忍度、RPO/RTO、實際 owner 與審查者尚未提供。
- 在上述資訊補齊前，只能完成規劃；不得宣稱已可執行或已具備可接受的 rollback。

## Routing and Escalation

- Primary owner：資料庫／平台負責人（待指定）。
- Required reviewers：獨立資料庫或可靠性審查者；涉及個資、財務或受管制資料時另加安全／合規審查。
- 本目錄是後續 session 的手動交接入口；後續執行者應先更新 PLAN 與 EVIDENCE，且不得將此草稿視為自動授權。
