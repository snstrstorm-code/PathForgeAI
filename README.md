# PathForge AI — standalone backend

This makes PathForge AI work from any browser, on any host — no dependency
on Claude.ai. It's the FastAPI backend your own pitch deck already planned
for: it holds your Groq API key server-side and proxies the two AI
calls (skill extraction + roadmap generation) that the frontend needs.

## What's here

```
backend/
  server.py          FastAPI app — /api/analyze, /api/roadmap, /api/health
  requirements.txt
  .env.example        copy to .env or export the vars yourself
  static/index.html   the PathForge AI frontend, wired to call this backend
```

## Run it

```bash
cd backend
pip install -r requirements.txt
export GROQ_API_KEY=gsk_your-key-here             # see .env.example
uvicorn server:app --reload --port 8000
```

Open **http://localhost:8000** — that's it. The backend serves the frontend
at `/` and the API at `/api/*`, so there's nothing else to configure.

Check `http://localhost:8000/api/health` any time to confirm the key is
loaded (`"key_configured": true`) without spending a request.

## Hosting the frontend and backend separately

If you'd rather deploy `static/index.html` somewhere else (e.g. GitHub
Pages) and point it at a backend running elsewhere:

1. Open `static/index.html`, find `const API_BASE = '';` near the top of
   the `<script>` block, and set it to your backend's URL, e.g.
   `const API_BASE = 'https://your-backend.onrender.com';`
2. The backend already has CORS wide open (`allow_origins=["*"]`) so this
   works out of the box. Tighten that to your actual frontend origin before
   you consider this production-ready.

## Deploying

Any host that runs a Python web service works — Render, Railway, Fly.io, a
plain VM, etc. The important part: set `GROQ_API_KEY` as an
environment variable / secret on that host. Never put the key in the HTML
file or commit it to git — that's the entire reason this backend exists.

## If the AI call fails

Same behavior as before: the frontend automatically falls back to a local
heuristic analysis (no AI, but never broken) and shows a small banner
saying so. Check `/api/health` and your server logs first — the most common
cause is a missing or invalid `GROQ_API_KEY`.

## Notes

- Model used: `openai/gpt-oss-120b` (Groq free tier) (override with the `PATHFORGE_MODEL` env
  var if you want a different one).
- `max_tokens` is capped at 1000 per call by design — both prompts are
  written to fit comfortably within that.
- This is a small proxy, not a production backend: no auth, no rate
  limiting, no persistence. Your own deck's plan (MySQL for saved
  roadmaps, auth for individual learners) is the natural next layer on top
  of this.
