# SkillSwap Product Backlog

A credit-based peer skill exchange platform built with Next.js 14 App Router, FastAPI backend, Supabase Postgres with pgvector, and Upstash Redis.

## Sprint Roadmap (7 Sprints)

| Sprint | Focus / Goal | Committed Stories | Story Points | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Sprint 1** | **Foundation, Identity & Wallet**: Setup, Auth/SSO, Profiles, Double-entry Wallet | US-01, US-02, US-04 | 9 | **Done** |
| **Sprint 2** | **Availability & Discovery**: Mentor slots, Semantic Search with pgvector, Mentor Profiles | US-08, US-05, US-07 | 15 | **Done** |
| **Sprint 3** | **Booking & Escrow Core**: Slot locking with Redis mutex, Escrow RPC, Low-balance alerts | US-10, US-11, US-13 | 12 | Todo |
| **Sprint 4** | **Live Session Collaboration**: Jitsi JWT integration, Session room, Code editor & Whiteboard | US-14, US-15 | 13 | Todo |
| **Sprint 5** | **Settlement, No-Show & Feedback**: Dual sign-off, No-show auto-refund, Mutual rating/review | US-16, US-17, US-18 | 13 | Todo |
| **Sprint 6** | **Disputes & Governance**: Dispute filing, Admin arbitration console, Zero-sum ledger audit | US-19, US-20, US-21 | 11 | Todo |
| **Sprint 7** | **Trust & Enhancements**: Skill quiz, Reciprocal matching filter, Calendar export/sync, Badges | US-03, US-06, US-09, US-12, US-22 | 17 | Todo |

**Total Estimated Points: 90 points across 22 User Stories (24 Completed across Sprints 1 & 2)**

---

## User Stories

| Story ID | Epic | Title | Priority | Points | Sprint | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **US-01** | Account & Profile | Sign in with Campus SSO | High | 3 | Sprint 1 | **done** |
| **US-02** | Account & Profile | Manage skill profile | High | 3 | Sprint 1 | **done** |
| **US-03** | Account & Profile | Take initial skill quiz | Med | 3 | Sprint 7 | todo |
| **US-04** | Account & Profile | View wallet and history | High | 3 | Sprint 1 | **done** |
| **US-05** | Search & Matching | Search mentors by learning goal | High | 8 | Sprint 2 | **done** |
| **US-06** | Search & Matching | Filter and compare mentors | Med | 3 | Sprint 7 | todo |
| **US-07** | Search & Matching | View mentor profile | High | 2 | Sprint 2 | **done** |
| **US-08** | Mentor Availability| Publish slots and rate | High | 5 | Sprint 2 | **done** |
| **US-09** | Mentor Availability| Sync with Google Calendar | Low | 5 | Sprint 7 | todo |
| **US-10** | Booking & Escrow | Book a session slot | High | 8 | Sprint 3 | todo |
| **US-11** | Booking & Escrow | See clear low-balance message | High | 2 | Sprint 3 | todo |
| **US-12** | Booking & Escrow | Receive calendar invite and reminder | Med | 3 | Sprint 7 | todo |
| **US-13** | Booking & Escrow | Receive booking alert | High | 2 | Sprint 3 | todo |
| **US-14** | Live Session | Join a video session | High | 8 | Sprint 4 | todo |
| **US-15** | Live Session | Use code editor and whiteboard | Med | 5 | Sprint 4 | todo |
| **US-16** | Settlement & Reviews | Get credits after a session | High | 5 | Sprint 5 | todo |
| **US-17** | Settlement & Reviews | Auto-refund on no-show | High | 5 | Sprint 5 | todo |
| **US-18** | Settlement & Reviews | Rate and review the other person | Med | 3 | Sprint 5 | todo |
| **US-19** | Disputes & Admin | Raise a dispute | High | 3 | Sprint 6 | todo |
| **US-20** | Disputes & Admin | Arbitrate disputes | High | 5 | Sprint 6 | todo |
| **US-21** | Disputes & Admin | Audit the credit ledger | Med | 3 | Sprint 6 | todo |
| **US-22** | Reputation | Earn reputation badges | Low | 3 | Sprint 7 | todo |
