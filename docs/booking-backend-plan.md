# Plan — Booking Backend (Google Sheets + Availability + Guardrail)

The actionable plan for the next build phase. Decisions behind it live in
`architecture-decisions.md` (#11 business type, #12 booking backend, #13 guardrail).

**Business:** CityCare Clinic — a **doctor clinic (consultations only)**.
**Goal:** real, persistent, slot-aware bookings recorded in a team-visible Google Sheet,
with availability checks, alternative-slot suggestions, and a duplicate-booking guardrail.

**Legend:** 🧑 = Shahzain does manually · 🤖 = Claude does (code/docs)

---

## Data model — Google Sheet (2 tabs)

**Tab `Availability`** (doctor's weekly schedule — the business fills this):
| Day | Open | Close | SlotMinutes |
|---|---|---|---|
| Monday | 09:00 | 17:00 | 30 |
| … | | | |

**Tab `Bookings`** (confirmed appointments — the team's live dashboard):
| Date | Time | PatientName | Phone | Status | CreatedAt |
|---|---|---|---|---|---|
| 2026-07-06 | 17:00 | Ali | 923… | confirmed | … |

Dates: ISO `YYYY-MM-DD`. Times: 24-hour `HH:MM`. Capacity: 1 per slot (single doctor).

---

## Flow

```
Customer: "book kal 5pm, naam Ali"
   │
   ▼  check_slot(date, time)          ← Availability − already-booked
   ├── AVAILABLE
   │      → polite "team se confirm kar rahe" to customer
   │      → owner gets details + "YES <id> / NO <id>"
   │      → owner YES → append to Bookings + "✅ confirmed" to customer
   │
   └── NOT AVAILABLE
          → suggest_alternatives(): next open slots offered to customer
          → customer picks one → owner approval → append + confirm
```

**HITL:** the booking team approves every booking (unchanged). The AI just adds
slot-awareness + alternatives + the persistent record.

**Guardrail (ADK `before_tool_callback`):** before the booking tool runs, if this
phone already has a **pending/confirmed** booking → block + tell the customer they
already have one (no duplicate owner ping, no duplicate row).

---

## Files (following the existing `whatsapp_client.py` pattern)

| File | Purpose | Who |
|---|---|---|
| `whatsapp_fte/availability.py` | pure slot logic (free_slots, is_available, suggest_alternatives) — unit-testable, no I/O | 🤖 |
| `whatsapp_fte/sheets_client.py` | gspread wrapper: read Availability, read/append Bookings | 🤖 |
| `setup_sheet.py` | one-off: create tabs + dummy Availability data | 🤖 writes, 🧑 runs |
| `whatsapp_fte/webhook_agent.py` | add tools `check_slot`, `create_booking_request` + the `before_tool_callback` guardrail | 🤖 |
| `whatsapp_webhook/main.py` | owner-approval → append to Bookings + confirm customer | 🤖 |
| `business_profile.json` | trim to doctor-clinic (remove lab tests) | 🤖 |

---

## Build order (each step testable before the next)

1. 🤖 `availability.py` + offline unit test (fake data — no credentials needed).
2. 🤖 `sheets_client.py` + `setup_sheet.py`.
3. 🧑 Google setup (below) → run `setup_sheet.py` to seed dummy data.
4. 🤖 Agent tools (`check_slot`, `create_booking_request`) + available-path flow.
5. 🤖 Not-available → alternatives path.
6. 🤖 Guardrail callback (duplicate booking).
7. 🤖 Webhook owner-approval → append to Bookings sheet.
8. 🧑+🤖 End-to-end live WhatsApp test → **deploy** → **README/video/writeup**.

---

## Manual setup (🧑 — Claude cannot do these)

1. Create a **Google Sheet**; note its **URL/ID**.
2. **Service Account** (free): Google Cloud → enable **Sheets API + Drive API** →
   create SA → download **JSON key** → put it in `whatsapp_fte_agent/.secrets/`.
3. **Share** the Sheet with the service-account **email** (Editor).
4. Add to `whatsapp_fte/.env` (names only; values are yours):
   `GOOGLE_SA_KEY_PATH`, `BOOKING_SHEET_ID`.
5. Install deps: `gspread`, `google-auth`.
6. Run `setup_sheet.py` once to seed dummy data.

> Security: the SA key stays in `.secrets/` — Claude references its path and uses it
> in code, but never reads or displays its contents.

---

## Scope / deadline guard (submit Jul 7)

Steps 1–7 make the product real. If time runs short before submission artifacts,
**trim in this order:** alternatives path (5) → guardrail (6) → deploy. The
persistent Bookings sheet (7) + available-path (4) are the core wins. README + video
+ writeup are **non-negotiable** for submission.
