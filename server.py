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
(public/index.html, or served by Vercel's CDN in that deployment) AND the
/api/* endpoints it calls. Two ways in: /api/analyze takes typed text,
/api/analyze-pdf takes an uploaded PDF resume and extracts the text here on
the server before handing it to the model — nothing gets pasted into a
textarea for the user to see or edit.
"""
import json
import os
import re
from io import BytesIO

import requests
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pypdf import PdfReader

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.environ.get("PATHFORGE_MODEL", "openai/gpt-oss-120b")

MAX_PDF_BYTES = 8 * 1024 * 1024  # 8MB, matches the frontend's client-side check
MAX_PDF_PAGES = 15
MAX_RESUME_CHARS = 15000

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


def extract_pdf_text(file_bytes: bytes) -> str:
    """Pull selectable text out of a PDF resume. Raises ValueError with a
    user-facing message for anything that goes wrong (encrypted, scanned
    image with no text layer, corrupt file, etc.)."""
    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception:
        raise ValueError("That doesn't look like a valid PDF — try re-exporting it and uploading again.")

    if reader.is_encrypted:
        try:
            result = reader.decrypt("")
        except Exception:
            result = 0
        if not result:
            raise ValueError("This PDF is password-protected — remove the password and try again.")

    parts = []
    try:
        pages = reader.pages[:MAX_PDF_PAGES]
    except Exception:
        raise ValueError("This PDF is password-protected — remove the password and try again.")
    for page in pages:
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            parts.append(t)

    text = "\n\n".join(parts)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not text:
        raise ValueError(
            "Couldn't find any selectable text in that PDF — it may be a scanned image. "
            "Try the \"Type it in\" option instead."
        )
    return text[:MAX_RESUME_CHARS]


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
                "max_tokens": 1000,
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


def run_analyze(target_role: str, resume_text: str, skills_text: str, projects_text: str) -> dict:
    user_msg = (
        f"Target role: {target_role}\n\n"
        f"Resume:\n{resume_text or '(none provided)'}\n\n"
        f"Self-listed skills:\n{skills_text or '(none provided)'}\n\n"
        f"Projects:\n{projects_text or '(none provided)'}"
    )
    out = call_ai(ANALYZE_SYSTEM, user_msg)
    if "currentSkills" not in out or "requiredSkills" not in out:
        raise HTTPException(status_code=502, detail="Model response missing expected fields.")
    return out


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    return run_analyze(req.targetRole, req.resumeText, req.skillsText, req.projectsText)


@app.post("/api/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...), targetRole: str = Form(...)):
    """Same as /api/analyze, but the resume comes from an uploaded PDF
    instead of typed text. The file never round-trips through the browser
    as visible text — it's read here and handed straight to the model."""
    if file.content_type not in ("application/pdf", "application/x-pdf", "binary/octet-stream") and not (
        file.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    data = await file.read()
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="That file is too large — try one under 8MB.")

    try:
        resume_text = extract_pdf_text(data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return run_analyze(targetRole, resume_text, "", "")


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


# On Vercel, the frontend (public/index.html) is served directly by
# Vercel's CDN, not through FastAPI — see public/ below. This file only
# needs to define the /api/* routes above.
