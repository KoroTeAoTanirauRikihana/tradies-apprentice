# The Tradie's Apprentice - Public App

Free, public knowledge-consultation app for home electrical and plumbing
trades, tools, and real DIY conversion knowledge (EVs, boats, aircraft,
phones, maglev demos) - a companion to The Tohunga's Apprentice (Māori
tradition) and The Seer's Apprentice (Norse/Celtic tradition). Standalone
from Koro Global Hub for the same reason as the other two: the Hub holds
private tasks/family info/other workers that should never face the
public internet.

Real source of knowledge: `Documents\Electrician_Apprentice_Vault\Knowledge\`
(Koro's own dedicated Obsidian vault, real wiki-linked notes with topic
tags). `backend/sync_knowledge.py` pulls a filtered snapshot - never a
live path into his machine.

## The one rule that governs everything in the knowledge base

Every file draws an explicit, hard line between real safe DIY/
troubleshooting territory and "this needs a licensed professional, not
me" territory. This agent never claims to be a licensed electrician or
plumber, and safety steps (de-energise, isolate water, discharge
capacitors) are always stated as the real first step of a process, never
a buried disclaimer.

## What's actually built and tested, 2026-08-28

- `backend/app.py` - real Flask API (`POST /ask`, `GET /api/status`),
  same knowledge base and honesty system prompt as the private Hub worker
  (`workers/electrician_apprentice.py`). Reads `OPENAI_API_KEY` from
  environment (its own funded key). Real retrieval (`_retrieve_relevant`)
  scores knowledge sections by keyword/domain-tag relevance rather than
  dumping the whole ~150k-character knowledge base into every prompt.
- `backend/sync_knowledge.py` - pulls a filtered snapshot from the
  private vault. **Tested live**: synced 32 files.
- **Tested live**: backend boots, `/api/status` correct, web app served
  at `/` (200, real HTML, correct title) with the backend running.
- `app/` - real Expo SDK 57 project, full working chat UI.
  **Verified via a real `npx expo export --platform web` build - exit 0,
  197 modules bundled clean.**

## What's genuinely NOT done yet

1. A real, funded `OPENAI_API_KEY` for this app specifically.
2. A real hosting decision (Render/Railway/Fly.io are the cheap options
   already scoped for the other two apps).
3. Its own Cloudflare tunnel.
4. A real Expo project link (`eas init`) - only needed for an Android
   APK build; deliberately not done yet, same reasoning as the Seer's
   Apprentice app - needs Koro's call on which Expo account owns it.

## Local dev

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python sync_knowledge.py
$env:PORT = "8422"
.venv\Scripts\python app.py
```
