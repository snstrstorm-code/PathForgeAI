"""
PathForge AI — backend proxy
=============================
A small FastAPI service that stands between the PathForge AI frontend and the
Groq API (free tier, OpenAI-compatible). It holds the real Groq API key
server-side (never in the browser), does the same two AI calls the frontend used to make directly
(skill extraction + role mapping, then roadmap generation), and returns
clean JSON the frontend already knows how to render.

Run it:
    pip install -r requirements.txt
    export GROQ_API_KEY=gsk_...      (see .env.example)
    uvicorn server:app --reload --port 8000

Then open http://localhost:8000 — this serves the PathForge AI frontend
(static/index.html) AND the /api/* endpoints it calls, so there's nothing
else to wire up. If you'd rather host the frontend elsewhere, CORS is open
below — just point PathForge's API_BASE (near the top of its <script>) at
this server's URL.
"""
import io
import json
import os
import re

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.environ.get("PATHFORGE_MODEL", "openai/gpt-oss-120b")
MAX_RESUME_FILE_BYTES = 8 * 1024 * 1024  # 8MB — matches the frontend's check

app = FastAPI(title="PathForge AI backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your frontend's origin before going to production
    allow_methods=["*"],
    allow_headers=["*"],
)

ANALYZE_SYSTEM = """You are the skill-extraction and role-mapping engine inside PathForge AI, a career-readiness platform. Given a learner's resume/skills/projects text and a target job role, output ONLY one raw JSON object, no markdown fences, no commentary, in exactly this shape:
{"currentSkills":[{"name":string,"level":number,"note":string}],"requiredSkills":[{"name":string,"importance":number}]}
Rules:
- currentSkills: 6 to 10 items, real technical/professional skills inferred from the learner's resume, listed skills and project descriptions. level is 0-100, your estimate of proficiency from depth of evidence. note is at most 8 words of brief evidence.
- requiredSkills: 6 to 10 items, the most important skills/tools for the target role today. importance is 0-100 for how critical that skill typically is.
- Where a skill genuinely overlaps between the learner and the role, use the EXACT SAME name string in both arrays so they can be matched by a program.
- Use short canonical skill names (e.g. "React", "SQL", "System Design"), not sentences.
- Output raw JSON only, nothing else."""

ROADMAP_SYSTEM = """You are the AI Roadmap Engine inside PathForge AI. Given a learner's skill gaps for a target role, output ONLY one raw JSON object, no markdown fences, no commentary, in exactly this shape:
{"roadmap":[{"skill":string,"status":"critical"|"developing","weeks":number,"learn":string,"practice":string,"build":string,"validate":string}]}
Rules:
- At most 8 items, ordered by priority — most critical / highest-impact first. This order is the sequence the learner should follow.
- weeks is an integer 1-6 estimate to close that gap.
- learn = a specific concept or resource-type action, max 10 words. practice = a specific drill or exercise, max 10 words. build = a specific small project to build, max 10 words. validate = a specific way to prove the skill (assessment, portfolio piece, mock task), max 10 words.
- Tailor everything to the given target role.
- Output raw JSON only, nothing else."""


class AnalyzeRequest(BaseModel):
    targetRole: str
    resumeText: str = ""
    skillsText: str = ""
    projectsText: str = ""


class GapItem(BaseModel):
    skill: str
    status: str
    currentLevel: float = 0
    importance: float = 0


class RoadmapRequest(BaseModel):
    targetRole: str
    gaps: list[GapItem] = Field(default_factory=list)


def extract_json(text: str) -> dict:
    """Same tolerant parser the frontend uses: strip code fences, grab the
    outermost {...} block, parse it. Raises ValueError on anything that
    doesn't look like a single JSON object."""
    cleaned = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model output")
    return json.loads(cleaned[start : end + 1])


def call_ai(system: str, user: str) -> dict:
    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GROQ_API_KEY is not set on the server. See .env.example.",
        )
    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 2000,
                "reasoning_effort": "low",
                "reasoning_format": "hidden",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=30,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Could not reach Groq API: {e}")

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Groq API returned {resp.status_code}: {resp.text[:300]}",
        )

    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError):
        raise HTTPException(status_code=502, detail="Unexpected response shape from Groq API.")
    try:
        return extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=502, detail=f"Model did not return valid JSON: {e}")


@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL, "key_configured": bool(GROQ_API_KEY)}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    user_msg = (
        f"Target role: {req.targetRole}\n\n"
        f"Resume:\n{req.resumeText or '(none provided)'}\n\n"
        f"Self-listed skills:\n{req.skillsText or '(none provided)'}\n\n"
        f"Projects:\n{req.projectsText or '(none provided)'}"
    )
    out = call_ai(ANALYZE_SYSTEM, user_msg)
    if "currentSkills" not in out or "requiredSkills" not in out:
        raise HTTPException(status_code=502, detail="Model response missing expected fields.")
    return out


def extract_pdf_text(data: bytes) -> str:
    """Pull plain text out of a PDF's pages. Raises ValueError with a
    user-facing message on anything that isn't a readable, unlocked PDF."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError:
        raise ValueError("That doesn't look like a valid PDF file.")

    if reader.is_encrypted:
        try:
            # Try an empty password — covers PDFs "protected" with no real password.
            reader.decrypt("")
        except Exception:
            raise ValueError("That PDF is password-protected — please upload an unlocked copy.")

    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n\n".join(parts).strip()


@app.post("/api/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...), targetRole: str = Form(...)):
    if not targetRole.strip():
        raise HTTPException(status_code=400, detail="Missing target role.")

    is_pdf = (file.content_type == "application/pdf") or (file.filename or "").lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    data = await file.read()
    if len(data) > MAX_RESUME_FILE_BYTES:
        raise HTTPException(status_code=400, detail="That PDF is too large — please upload a file under 8MB.")
    if not data:
        raise HTTPException(status_code=400, detail="That file came through empty — please try again.")

    try:
        resume_text = extract_pdf_text(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not resume_text:
        raise HTTPException(
            status_code=422,
            detail="Couldn't find any readable text in that PDF — it may be a scanned image. "
                   "Try another file or switch to \"Type it in\".",
        )
    if len(resume_text) > 6000:
        resume_text = resume_text[:6000]

    user_msg = (
        f"Target role: {targetRole}\n\n"
        f"Resume (extracted from uploaded PDF):\n{resume_text}\n\n"
        f"Self-listed skills:\n(none provided)\n\n"
        f"Projects:\n(none provided)"
    )
    out = call_ai(ANALYZE_SYSTEM, user_msg)
    if "currentSkills" not in out or "requiredSkills" not in out:
        raise HTTPException(status_code=502, detail="Model response missing expected fields.")
    return out


@app.post("/api/roadmap")
def roadmap(req: RoadmapRequest):
    gap_lines = "\n".join(
        f"{g.skill} (status:{g.status}, current:{g.currentLevel}, needed:{g.importance})"
        for g in req.gaps
    )
    user_msg = f"Target role: {req.targetRole}\n\nSkill gaps to close, in no particular order:\n{gap_lines}"
    out = call_ai(ROADMAP_SYSTEM, user_msg)
    if "roadmap" not in out:
        raise HTTPException(status_code=502, detail="Model response missing expected fields.")
    return out


# Serve the PathForge AI frontend itself at "/" — copy PathForge_AI.html into
# backend/static/index.html (done automatically if you use the provided
# folder layout). API routes above are registered first so they always win.
if os.path.isdir(os.path.join(os.path.dirname(__file__), "static")):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
