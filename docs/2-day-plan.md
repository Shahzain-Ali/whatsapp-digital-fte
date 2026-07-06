# 2-Day Build Plan — WhatsApp Digital FTE (Capstone)

**Deadline:** submit Jul 7. **Build:** Jul 5–6. **Writeup + video + submit:** Jul 7 morning.

**Legend:** 🧑 = Shahzain does manually (logins/keys/recording) · 🤖 = Claude does (code/docs)

---

## ✅ STATUS (Jul 5) — Core system DONE + LIVE

Multi-agent + MCP + preloaded KB + HITL are built, and the **real WhatsApp webhook
is live and verified** end-to-end (inbound → AI reply → cross-channel owner approval
→ confirmation), including a network fix for flaky WhatsApp send (retries) — see
`troubleshooting-log.md`. Remaining LLM latency (~50s from this ISP) is a known,
optional item.

**Current phase → Booking Backend** (Google Sheets + availability + guardrail):
full plan in **`booking-backend-plan.md`**. After that: **deploy** → **README** →
**video** → **writeup**.

---

## DAY 1 (Jul 5) — Core Agent System

**Goal by end of day:** Multi-agent + MCP + Knowledge Base running locally in `adk web`.

| Block | Time | Task | Who |
|---|---|---|---|
| 1 | ~1h | Project scaffold: folders, `requirements.txt`, `.env` variable NAMES, model config | 🤖 |
| 1 | ~15m | Add API keys to `.env` (OpenAI/Gemini) | 🧑 |
| 2 | ~2h | **Onboarding Agent** — ingests business info (text/file), builds Knowledge Base (preloaded) | 🤖 |
| 3 | ~2.5h | **WhatsApp MCP Server** — `send_message`, `get_messages` tools (mock first) | 🤖 |
| 4 | ~2h | **WhatsApp Agent** (uses MCP tools + preloaded KB) + **Orchestrator** (sub-agents) | 🤖 |
| 5 | ~1h | Test full flow in `adk web` (onboard → customer question → answer) | 🤖 |

**Day 1 deliverable:** working multi-agent system, MCP tools firing, KB answering — locally.

---

## DAY 2 (Jul 6) — Security, Deploy, Polish

**Goal by end of day:** HITL working, connected/demoed, video recorded, README done.

| Block | Time | Task | Who |
|---|---|---|---|
| 1 | ~2h | **HITL approval** (`request_confirmation`) for sensitive actions (booking/confirm) — test approve + reject | 🤖 |
| 2 | ~30m | Create Meta Business + Developer App → **WhatsApp test number (sandbox)** | 🧑 |
| 2 | ~1.5h | Connect sandbox (webhook via ngrok) **OR** finalize `adk web` simulation → end-to-end test | 🤖 |
| 3 | ~1.5h | *(Optional)* Deploy to Vertex AI Agent Engine — else document the deploy steps | 🤖 + 🧑 login |
| 4 | ~1.5h | **README.md** + architecture diagram | 🤖 |
| 5 | ~30m | Write the 5-min **video script** | 🤖 |
| 5 | ~1.5h | **Record screen demo** + narrate + upload to YouTube | 🧑 |

**Day 2 deliverable:** secure, demoable agent + README + diagram + YouTube video.

---

## DAY 3 (Jul 7, morning) — Writeup + Submit

| Time | Task | Who |
|---|---|---|
| ~1.5h | **Writeup draft** (≤2,500 words): problem → solution → architecture → journey | 🤖 |
| ~30m | Polish writeup in your voice + pick **cover image** | 🧑 |
| ~30m | Create Kaggle Writeup → attach cover image, YouTube video, GitHub link → select **Agents for Business** track | 🧑 |
| — | **Hit Submit** (before deadline — draft doesn't count) | 🧑 |

---

## Course concepts hit (need 3, we do 5)
Multi-agent (ADK) ✅ · MCP Server ✅ · Security/HITL ✅ · Deployability ✅ · Agents CLI (`adk web`/`adk run`) ✅

## Guaranteed-safe fallbacks (so we never miss the deadline)
- WhatsApp sandbox stalls → **simulate the channel in `adk web`** (same architecture, judges still see the flow).
- Deploy stalls → **document deploy steps** (capstone doesn't require a live endpoint).
