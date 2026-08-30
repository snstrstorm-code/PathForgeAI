# PathForge AI

**AI-powered career readiness platform** — built by **Team Vendetta** for **Smart India Hackathon 2026**.

PathForge AI analyzes a learner's resume, existing skills, projects, and target role to identify skill gaps against real industry requirements, then generates a personalized, continuously adaptive learning roadmap — sequenced as **Learn → Practice → Build → Validate** — that updates automatically as the learner progresses.

---

## The Problem

- Learners often study without knowing what skills they actually lack.
- Generic roadmaps don't account for a learner's current abilities and past projects.
- The same target role requires different learning paths for different people.

## Our Solution

PathForge AI creates a personalized, dynamically adapting roadmap for every learner. When a learner gains a new skill or completes a project, the AI reassesses the remaining gaps and updates the next steps — the roadmap never goes stale.

---

## How It Works

1. **Input** — learner submits resume, self-listed skills, projects, and a target role.
2. **Skill Extraction** — AI identifies skills, tools, and technologies from the input.
3. **Skill Profiling** — estimates the learner's current proficiency per skill.
4. **Role Mapping** — maps the target role to the skills it requires.
5. **Gap Analysis** — compares current vs. required skills to flag Critical / Developing / Strong gaps.
6. **AI Roadmap Engine** — prioritizes, sequences, and recommends a stage-by-stage plan.
7. **Feedback Loop** — learner logs new skills/completed projects; the roadmap reassesses automatically.

---

## Tech Stack

| Layer      | Technology                           |
|------------|--------------------------------------|
| Frontend   | HTML                                 |
| Backend    | HTML                                 |
| AI         | Meta Llama API                       |
| Deployment | Vercel                               |

---

## Getting Started (Local Setup)

### Prerequisites
- Python 3.11+

### 1. Clone the repo
```bash
git clone https://github.com/<your-username>/pathforge-ai.git
cd pathforge-ai
```

### 2. Set up a virtual environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure your API key
Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_key_here
```

### 5. Run the app
```bash
uvicorn main:app --reload
```

Open **http://127.0.0.1:8000** in your browser.

---

## API Endpoints

| Method | Endpoint         | Description                                      |
|--------|------------------|---------------------------------------------------|
| POST   | `/api/analyze`   | Extracts current skills and required skills for a target role |
| POST   | `/api/roadmap`   | Generates a sequenced learning roadmap from skill gaps |
| POST   | `/upload-resume` | Extracts text from an uploaded PDF resume for analysis |

---

## Impact

| Students | Institutions | Industry |
|----------|--------------|----------|
| Personalized learning direction | Identify recurring skill gaps | Better role-skill alignment |
| Clear skill priorities | Support targeted training | More job-ready candidates |
| Relevant project recommendations | Improve placement preparation | Stronger practical portfolios |
| Reduced random learning | Track learner progress | |

---

## Research & References

- [World Economic Forum — Future of Jobs Report 2025](https://www.weforum.org/publications/the-future-of-jobs-report-2025/)
- [NACE — Career Readiness Competencies](https://www.naceweb.org/career-readiness/competencies/career-readiness-defined/)
- [LinkedIn — Workplace Learning Report](https://learning.linkedin.com/resources/workplace-learning-report)
- [Coursera — Global Skills Report 2025](https://www.coursera.org/skills-reports/global)

---

## Team Vendetta

Built for Smart India Hackathon 2026.
