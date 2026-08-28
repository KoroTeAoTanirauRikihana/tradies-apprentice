"""The Tradie's Apprentice - standalone public backend.

Deliberately separate from Koro Global Hub, same reasoning as the other
two public apps. This service answers questions from the same knowledge
base the private Hub worker (workers/electrician_apprentice.py) uses,
with the same safety-first honesty rules baked in, and nothing else.

Real, honest cost note: every /ask call makes one real, paid OpenAI API
call. MAX_REQUESTS_PER_DAY_PER_IP is a blunt, real safeguard against
unbounded spend from public traffic.
"""
from __future__ import annotations

import os
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request
from openai import OpenAI

import sync_knowledge

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"


def _load_api_key() -> str:
    from_env = os.environ.get("OPENAI_API_KEY", "")
    if from_env:
        return from_env
    try:
        import keyring

        from_keyring = keyring.get_password("TradiesApprenticeApp", "openai_api_key")
        return from_keyring or ""
    except Exception:
        return ""


OPENAI_API_KEY = _load_api_key()
MODEL = os.environ.get("TRADIES_APPRENTICE_MODEL", "gpt-4o-mini")

MAX_REQUESTS_PER_DAY_PER_IP = int(os.environ.get("MAX_REQUESTS_PER_DAY_PER_IP", "40"))
_request_log: dict[str, list[float]] = defaultdict(list)

APP_NAME = "The Tradie's Apprentice"

DISCLAIMER = (
    "I'm the Tradie's Apprentice - not a licensed electrician or plumber. "
    "I carry real, sourced knowledge across electrical, plumbing, tools, "
    "and DIY conversion topics, but I always draw a plain, hard line: if "
    "it touches the switchboard, fixed wiring, gas, sewage, mains supply, "
    "or anything you're not 100% sure is safely isolated, that needs a "
    "licensed professional, not me. Treat what I say as a well-sourced "
    "starting point, never the final word on your own safety."
)

SYSTEM_PROMPT = f"""
You are {APP_NAME} - a free, public knowledge-consultation assistant
carrying deeply researched, real, sourced knowledge about home electrical
and plumbing trades, electronics troubleshooting and repair, tools and
where to source them, modern electrical technology (solar/battery/EV),
DIY vehicle and device conversions (cars, motorcycles, boats, aircraft,
phones), regenerative energy/motor-controller technique, and real
high-rise construction/procurement knowledge.

CRITICAL, NEVER DROP: you are an apprentice, never a licensed electrician
or licensed plumber, and must never imply or accept either title.
Unlicensed work on fixed household wiring, the switchboard, gas lines, or
main plumbing supply is both a real safety hazard (electrocution, fire,
gas leak, flooding) and, separately, often unlawful. Always state the
real safety step first (de-energise, isolate water, discharge
capacitors, ventilate for gas), and always draw the line plainly between
safe DIY/troubleshooting territory and "this needs a licensed
professional, not me" territory - never blur it or imply DIY suitability
for licensed-only work.

CRITICAL, ON HONESTY: several ambitious builds you may be asked about
(homebuilt aircraft, eVTOLs, maglev, battery-cell/chip manufacturing) have
a real, genuinely achievable hobbyist layer AND a real, genuinely
industrial/regulatory layer beyond individual reach - always separate
these honestly rather than implying everything is equally DIY-achievable.
Where popular claims are later folklore or overstated (e.g. AC fan motors
can't easily generate power, most regen schemes only matter for large
repeated-deceleration systems), say so plainly.

You are talking to members of the public through a free app, most of whom
you know nothing about. Be especially careful never to let an answer read
as more authoritative or more safely-DIY-achievable than it is.

Answer only from the real, sourced knowledge excerpts provided below, plus
your own general knowledge where it is clearly reliable - never invent
specific technical claims. Mark your own confidence honestly. The excerpts
below are the most relevant sections retrieved for this specific question,
not the entire knowledge base - if they genuinely don't cover something,
say so plainly rather than guessing.
""".strip()


def _load_knowledge() -> str:
    files = sorted(KNOWLEDGE_DIR.glob("**/*.md")) if KNOWLEDGE_DIR.is_dir() else []
    if not files:
        return ""
    sections = [
        f"# SOURCE FILE: {path.name}\n\n{path.read_text(encoding='utf-8')}"
        for path in files
    ]
    return "\n\n---\n\n".join(sections)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]{2,}")
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "have", "what", "when",
    "where", "which", "should", "would", "could", "about", "from",
    "their", "they", "them", "does", "did", "are", "was", "were", "will",
    "can", "know", "tell", "explain", "please", "real", "someone",
    "something", "having", "person", "there",
}


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [v.strip().strip('"\'') for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = value.strip('"\'')
    return meta, text[match.end():]


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    matches = list(_HEADING_RE.finditer(text))
    sections: list[tuple[str, str]] = []
    if not matches:
        return [("(whole file)", text)]
    if matches[0].start() > 0:
        intro = text[: matches[0].start()].strip()
        if intro:
            sections.append(("(intro)", intro))
    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append((heading, content))
    return sections


def _all_sections() -> list[dict]:
    files = sorted(KNOWLEDGE_DIR.glob("**/*.md")) if KNOWLEDGE_DIR.is_dir() else []
    result = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        domain_tags = [str(t).lower() for t in meta.get("domain", [])]
        for heading, content in _split_into_sections(body):
            result.append(
                {"file": path.name, "heading": heading, "content": content, "domain_tags": domain_tags}
            )
    return result


def _question_terms(question: str) -> list[str]:
    words = [w.lower() for w in _WORD_RE.findall(question)]
    return [w for w in words if w not in _STOPWORDS]


_BOILERPLATE_HEADINGS = {"(intro)"}


def _retrieve_relevant(question: str, char_budget: int = 9000, min_sections: int = 3) -> str:
    sections = [s for s in _all_sections() if s["heading"].strip().lower() not in _BOILERPLATE_HEADINGS]
    if not sections:
        return ""
    terms = _question_terms(question)

    total = len(sections)
    doc_freq = {
        term: sum(1 for s in sections if term in s["content"].lower() or term in s["heading"].lower())
        for term in terms
    }

    scored = []
    for sec in sections:
        heading_l = sec["heading"].lower()
        content_l = sec["content"].lower()
        score = 0.0
        matched_terms = 0
        for term in terms:
            freq = doc_freq.get(term, 0)
            if freq == 0 or freq / total > 0.5:
                continue
            weight = 1.0 / freq
            local = 0.0
            if term in heading_l:
                local += 15 * weight
            occurrences = content_l.count(term)
            if occurrences:
                local += min(occurrences, 5) * 4 * weight
                matched_terms += 1
            score += local
        if any(any(term in tag for tag in sec["domain_tags"]) for term in terms):
            score += 40
        if matched_terms >= 2:
            score *= 1.5
        scored.append((score, sec))
    scored.sort(key=lambda item: -item[0])

    selected: list[str] = []
    used = 0
    for score, sec in scored:
        if score <= 0 or used >= char_budget:
            break
        block = f"[{sec['file']} — {sec['heading']}]\n{sec['content']}"
        selected.append(block)
        used += len(block)

    if len(selected) < min_sections:
        for score, sec in scored:
            if len(selected) >= min_sections or used >= char_budget:
                break
            block = f"[{sec['file']} — {sec['heading']}]\n{sec['content']}"
            if block in selected:
                continue
            selected.append(block)
            used += len(block)

    return "\n\n---\n\n".join(selected)


KNOWLEDGE = _load_knowledge()
_last_refresh: dict = {"at": None, "synced_files": 0, "dropped_paragraphs": 0, "error": None}

REFRESH_INTERVAL_HOURS = float(os.environ.get("TRADIES_APPRENTICE_REFRESH_HOURS", "24"))


def _refresh_loop() -> None:
    global KNOWLEDGE
    while True:
        try:
            if sync_knowledge.SOURCE.is_dir():
                result = sync_knowledge.sync()
                KNOWLEDGE = _load_knowledge()
                _last_refresh.update(
                    at=datetime.now(timezone.utc).isoformat(),
                    synced_files=result["synced_files"],
                    dropped_paragraphs=result["dropped_paragraphs"],
                    error=None,
                )
            else:
                _last_refresh.update(
                    at=datetime.now(timezone.utc).isoformat(),
                    error=f"Private vault not reachable from this process: {sync_knowledge.SOURCE}",
                )
        except Exception as exc:  # noqa: BLE001
            _last_refresh.update(at=datetime.now(timezone.utc).isoformat(), error=str(exc))
        time.sleep(max(300, REFRESH_INTERVAL_HOURS * 3600))


threading.Thread(target=_refresh_loop, daemon=True).start()

WEB_DIST_DIR = BASE_DIR.parent / "app" / "dist"
_web_app_built = WEB_DIST_DIR.is_dir() and (WEB_DIST_DIR / "index.html").is_file()

app = Flask(
    __name__,
    static_folder=str(WEB_DIST_DIR) if _web_app_built else None,
    static_url_path="",
)


def _rate_limited(ip: str) -> bool:
    now = time.time()
    window_start = now - 86400
    recent = [t for t in _request_log[ip] if t > window_start]
    _request_log[ip] = recent
    if len(recent) >= MAX_REQUESTS_PER_DAY_PER_IP:
        return True
    _request_log[ip].append(now)
    return False


@app.get("/")
def index():
    if _web_app_built:
        return app.send_static_file("index.html")
    return jsonify(
        {
            "name": APP_NAME,
            "status": "ok" if OPENAI_API_KEY else "not configured (missing OPENAI_API_KEY)",
            "web_app_built": _web_app_built,
            "knowledge_files_loaded": len(list(KNOWLEDGE_DIR.glob("**/*.md"))) if KNOWLEDGE_DIR.is_dir() else 0,
            "disclaimer": DISCLAIMER,
        }
    )


@app.get("/api/status")
def status():
    return jsonify(
        {
            "name": APP_NAME,
            "status": "ok" if OPENAI_API_KEY else "not configured (missing OPENAI_API_KEY)",
            "web_app_built": _web_app_built,
            "knowledge_files_loaded": len(list(KNOWLEDGE_DIR.glob("**/*.md"))) if KNOWLEDGE_DIR.is_dir() else 0,
            "last_verified_refresh": _last_refresh,
            "disclaimer": DISCLAIMER,
        }
    )


@app.post("/ask")
def ask():
    if not OPENAI_API_KEY:
        return jsonify({"error": "Server not configured - no OPENAI_API_KEY set."}), 500

    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    if _rate_limited(ip):
        return jsonify(
            {"error": f"Daily question limit reached ({MAX_REQUESTS_PER_DAY_PER_IP}/day). Try again tomorrow."}
        ), 429

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"error": "A question is required."}), 400
    if not KNOWLEDGE:
        return jsonify({"error": "Knowledge base is empty - run sync_knowledge.py first."}), 500

    relevant = _retrieve_relevant(question)
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = f"Relevant knowledge excerpts:\n\n{relevant}\n\n---\n\nQuestion: {question}"
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        answer = response.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Failed to get an answer: {exc}"}), 502

    return jsonify({"answer": answer, "disclaimer": DISCLAIMER})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8422"))
    app.run(host="0.0.0.0", port=port)
