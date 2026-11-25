# Sprint 1 Report: Foundation, Identity & Wallet

## Sprint Overview
- **Goal**: Establish the core architecture, campus authentication flow, student profile management with skill catalog, and double-entry credit wallet.
- **Committed Stories**:
  - `US-01`: Sign in with Campus SSO (3 pts) — **DONE**
  - `US-02`: Manage skill profile (3 pts) — **DONE**
  - `US-04`: View wallet and history (3 pts) — **DONE**
- **Velocity Delivered**: 9 Story Points
- **Branch**: `sprint-1`
- **Status**: Completed

---

## Acceptance Criteria Verification Summary

| Story | Given / When / Then Acceptance Criteria | Status | Evidence |
| :--- | :--- | :--- | :--- |
| **US-01** | • Given I am logged out, when I visit `/login`, then I see Campus SSO login option.<br>• Given my credentials are valid, then I land on `/dashboard` with name shown.<br>• Given I sign in for first time, then account is created with 3 starter credits via mint transfer.<br>• Given invalid credentials, then a plain-language error is displayed. | **PASS** | `01_login_sso.png`<br>`02_dashboard_overview.png` |
| **US-02** | • Given I am on my profile, when I add a skill with level, then it is saved to offered/desired list.<br>• Given I edit or remove a skill, then the change is saved immediately.<br>• Given a required field is empty, then validation prevents submission and explains error. | **PASS** | `03_profile_initial.png`<br>`04_profile_with_skills.png` |
| **US-04** | • Given I open my wallet, then I see Available Balance (3.00 cr) and Escrow Balance (0.00 cr).<br>• Given transactions happen, they appear in history with timestamp, type, direction, and amount.<br>• Given history view, entries are arranged newest first.<br>• Given money rules, client never computes balances; zero-sum invariant holds (Delta = 0). | **PASS** | `05_wallet_ledger_vault.png`<br>`06_wallet_audit_verified.png` |

---

## Test Results & Quality Metrics
- **Automated Tests**: 14 tests passing (`pytest tests/`)
- **Ledger Coverage**: **96% test coverage** on `skillswap_ledger.py` (Exceeds DoD >= 70% threshold)
- **TypeScript**: 0 errors (`npx tsc --noEmit` exit code 0)
- **ESLint**: 0 warnings or errors (`npm run lint` clean)
- **Zero-Sum Solvency**: Invariant `SUM(accounts.balance) == 0` and `SUM(debits) == SUM(credits)` strictly verified by SQL/ledger triggers.

---

## Browser Demo Walkthrough Evidence

### 1. Campus SSO Login (`US-01`)
![Campus SSO Login](/home/sukhpreet/.gemini/antigravity-cli/brain/8464f033-e597-4b28-91e7-d8c5a1834244/screenshots/sprint-1/01_login_sso.png)

### 2. Student Dashboard with 3 Starter Credits (`US-01`)
![Student Dashboard](/home/sukhpreet/.gemini/antigravity-cli/brain/8464f033-e597-4b28-91e7-d8c5a1834244/screenshots/sprint-1/02_dashboard_overview.png)

### 3. Profile & Skills Management (`US-02`)
![Profile with Teaching & Learning Skills](/home/sukhpreet/.gemini/antigravity-cli/brain/8464f033-e597-4b28-91e7-d8c5a1834244/screenshots/sprint-1/04_profile_with_skills.png)

### 4. Time Credit Wallet & Zero-Sum Audit (`US-04`)
![Wallet Vault & Ledger](/home/sukhpreet/.gemini/antigravity-cli/brain/8464f033-e597-4b28-91e7-d8c5a1834244/screenshots/sprint-1/06_wallet_audit_verified.png)

---

## Retrospective

### What Went Well
- Clean separation between Next.js 14 client and Python FastAPI backend with zero-trust accounting.
- Double-entry ledger engine achieved 96% test coverage with automated zero-sum invariant auditing.
- Campus SSO onboarding immediately credits the new user with 3 credits minted via double-entry transaction.
- Headless browser demo automated and executed with screenshot evidence captured.

### What Could Be Improved
- In Sprint 2, connect mentor availability slot scheduling so learners can book specific calendar blocks.
- Prepare pgvector cosine similarity integration for goal-based mentor search.

### Action Items for Sprint 2
1. Formulate Sprint 2 implementation plan for US-08 (Publish slots and rate), US-05 (Search mentors by learning goal), and US-07 (View mentor profile).
2. Obtain user approval before beginning Sprint 2 coding.
