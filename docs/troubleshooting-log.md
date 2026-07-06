# Troubleshooting Log — Live WhatsApp Integration

Real problems hit while wiring the WhatsApp Digital FTE to a live phone, with the
root cause and the exact fix for each. Kept for the productized build so we never
lose a day to the same issue twice.

Environment: Windows + WSL2, project on `/mnt/e` (Windows drive), Python 3.14 in a
`uv` venv, network in Pakistan.

---

## 1. Agent/folder name with a hyphen crashes ADK
- **Symptom:** `ValueError: Invalid agent name 'whatsapp-fte-agent' ... must be valid Python identifiers`.
- **Cause:** ADK imports the agent package as a Python module; hyphens are illegal in identifiers.
- **Fix:** Use underscores everywhere — `whatsapp_fte_agent`, not `whatsapp-fte-agent`.

## 2. `adk web` can't find the agent
- **Symptom:** `No root_agent found for 'whatsapp_fte_agent'` / 500 error.
- **Cause:** `adk web` was run from the parent folder; the agents dir must *contain* the agent package.
- **Fix:** Run from inside the project (`adk web /mnt/e/kaggle/whatsapp_fte_agent`) and select the `whatsapp_fte` app.

## 3. MCP session fails to start on WSL
- **Symptom:** `Failed to create MCP session: unhandled errors in TaskGroup`.
- **Cause:** Booting the MCP subprocess + importing `mcp` off the `/mnt` Windows drive is slow; the default ~5s connection timeout is too short.
- **Fix:** `StdioConnectionParams(..., timeout=60)`.

## 4. uvicorn: "Missing argument 'APP'" / wrong working dir
- **Symptom:** `Error: Missing argument 'APP'`, or `ModuleNotFoundError: No module named 'whatsapp_webhook'`.
- **Cause:** Ran `uvicorn` without the app path, or from a directory where the package isn't importable.
- **Fix:** `uvicorn --app-dir /mnt/e/kaggle/whatsapp_fte_agent whatsapp_webhook.main:app --host 0.0.0.0 --port 8000`.

## 5. Port 8000 already in use
- **Symptom:** `[Errno 98] address already in use`.
- **Cause:** A previous uvicorn (or another process) still holds the port.
- **Fix:** Stop the old one (`Ctrl+C`, or `pkill -f "uvicorn.*whatsapp_webhook"`), then start again.

## 6. Webhook verification fails (403)
- **Symptom:** Meta: "The callback URL or verify token couldn't be validated"; log shows `GET /webhook ... 403`.
- **Cause:** The verify token Meta sends (what you typed in the form) didn't equal `WHATSAPP_VERIFY_TOKEN` in `.env` — and `.env` is read at startup.
- **Fix:** Make both identical (no quotes/spaces), then **restart uvicorn** so the new value is loaded.

## 7. Real messages don't reach the webhook (only the dashboard "Test" works)
- **Symptom:** `messages` field is Subscribed and the dashboard **Test** button delivers `POST /webhook`, but a real WhatsApp message triggers nothing.
- **Cause:** The WhatsApp Business Account was subscribed to Meta's **default app** ("WA DevX Webhook Events 1P App"), not to *our* app. Configuring the callback URL is app-level; the WABA→app subscription is separate.
- **Fix:** Subscribe our app to the WABA:
  `POST https://graph.facebook.com/v22.0/{WABA_ID}/subscribed_apps` (with our app token) → `{"success": true}`.
  Verify with `GET /{WABA_ID}/subscribed_apps` — our app ("FTE Apps") must appear.

## 8. Inbound works but the AI's reply never arrives
- **Symptom:** `POST /webhook 200` logged, but no reply on the phone. Direct send test:
  `ConnectTimeoutError ... graph.facebook.com ... (connect timeout=30)` after 30s.
- **Cause (diagnosed step by step):** graph.facebook.com resolves to several edge IPs; from this ISP **some IPs time out on connect while others connect in ~2s** — flaky IPv4. There is **no IPv6** for the host, so an "IPv6-only" attempt fails outright. Python `requests` used a single IP with a 30s connect timeout and gave up → send failed → no reply. (Inbound still worked because that path is Meta → ngrok → localhost, no outbound connect needed.)
- **Fix:** In `whatsapp_client.py`, use a shared `requests.Session` with a **short connect timeout (8s)** and **automatic retries** (`urllib3 Retry`, which re-resolves DNS and usually lands on a reachable IP). Result: send succeeds in ~2.5s.
- **Wrong turn (noted so we don't repeat):** first hypothesis was "IPv4 broken, force IPv6." A raw socket test disproved it — the host has no IPv6 at all; the real issue was flaky IPv4. Always verify with a raw test before coding a fix.

## 9. LLM (OpenAI) very slow from this network — still open
- **Symptom:** Each `gpt-4o-mini` call takes ~47–84s (normally 1–2s). LiteLLM also logs a timeout fetching its model-cost map from `raw.githubusercontent.com`.
- **Cause:** ISP-level throttling of OpenAI / GitHub hosts from this network (not a code bug; the same code is fast from other networks).
- **Status:** Replies do arrive, just slowly. Options to fix later: run over a **VPN**, **deploy to a cloud host** with good connectivity, or **switch the model to Google Gemini** (Google hosts are fast/accessible here; ADK is Gemini-native).

---

## Running notes / gotchas
- **`.env` is read at startup** — after editing it, always restart uvicorn.
- **ngrok free URL changes** on restart — re-paste `https://<new>.ngrok-free.app/webhook` into Meta if you restart ngrok.
- **24-hour window:** free-form replies only deliver if the customer messaged within the last 24h; the owner must also have an open window to receive approval requests.
- **Temporary token** expires ~24h — regenerate in Meta and restart uvicorn if sends start returning 401.
- **Two verified numbers** needed for the demo: customer and owner (booking team), both added as sandbox recipients.
- **Sender = the business test number** (`+1 555 074-4613`), not a personal-to-personal chat.
