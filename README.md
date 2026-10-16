# JobPilot

**Resume → Jobs → Interview for the Heilbronn Baden-Württemberg corridor.**
Bilingual (German + English), powered by Groq + GPT-OSS 120B.

JobPilot reads your resume, finds matching jobs from Germany's official job
database in the Heilbronn Baden-Württemberg area, and (next) prepares a tailored
interview for each role.

## 🎯 Features

| Step | Feature | Interface |
|------|---------|-----------|
| 1 | **Resume parser** — PDF → structured profile (DE + EN) | `resume_app.py` |
| 2 | **Job search** — live listings in the Heilbronn Baden-Württemberg corridor | `jobs_app.py` |
| 3 | **Matching** — rank jobs against the profile (DE + EN reasons) | library (`resume_jobs.match`) |
| 4 | **Interview prep** — bilingual questions, answer outlines, gap analysis | library (`resume_jobs.interview`) |
| 5 | **Cover letter** — Anschreiben (DE) + cover letter (EN) | library (`resume_jobs.cover_letter`) |
| 6 | **Find jobs from a JD** — paste a job posting → extract roles/skills → search + rank by similarity | tab (`streamlit_app.py`) |

> The earlier calculator / weather demo tools have been removed; see git history if needed.

## 🚀 Quick Start

```bash
git clone git@github.com:jiyan-0525/JobPilot.git
cd JobPilot

pip install -r requirements.txt
# create .env with your Groq key (job search needs no key):
#   GROQ_API_KEY=your_key_from_https://console.groq.com/keys

# Resume parser (tab 1)
.venv/bin/python -m streamlit run resume_app.py

# Job search (tab 2)
.venv/bin/python -m streamlit run jobs_app.py
```

## 🛠️ Tech Stack

- 🤖 AI Engine: Groq + GPT-OSS 120B (`openai/gpt-oss-120b`)
- 🌐 Web UI: Streamlit
- 📄 Resume: `pypdf` (text-based PDFs)
- 🔎 Jobs: Bundesagentur für Arbeit Jobsuche API (public key, no registration)
- 🧪 Testing: pytest + GitHub Actions CI
- 📦 Python: 3.10+

## 🏗️ Project Structure

```
JobPilot/
├── resume_app.py           # Streamlit: resume → profile
├── jobs_app.py             # Streamlit: job search corridor
├── resume_jobs/
│   ├── llm.py              # shared Groq client (lazy)
│   ├── schema.py           # profile schema + normalization
│   ├── resume.py           # extract_text() / parse_profile()
│   ├── jobs.py             # Arbeitsagentur client (search + details)
│   ├── arbeitnow.py        # Arbeitnow client (second source, no key)
│   ├── step.py             # step framing: run_step / run_step_tool (role/task/context)
│   ├── render.py           # profile_block / job_block
│   ├── match.py            # rank_jobs() — step 3
│   ├── jd_search.py        # find_jobs_from_jd() — JD → search + rank
│   ├── interview.py        # prepare_interview() — step 4
│   └── store.py            # JSON persistence (profiles, job caches)
├── rag.py                  # minimal RAG (question bank)
├── tests/                  # offline tests (no network, no API key)
├── requirements.txt
└── RESUME_JOBS.md          # full design doc & roadmap
```

## ⚙️ Environment

`.env`:

```
GROQ_API_KEY=gsk-your-groq-key-here
GROQ_MODEL=openai/gpt-oss-120b        # optional; defaults to openai/gpt-oss-120b
```

- **Groq** → fast OpenAI-compatible inference (free tier).
- **`GROQ_MODEL`** → optional model override. Free-tier daily token caps are
  per-model, so switching (e.g. `openai/gpt-oss-20b`) sidesteps a TPD 429
  without touching code.
- **Bundesagentur für Arbeit Jobsuche API** → free, public, no key required
  (`X-API-Key: jobboerse-jobsuche`).

## 🗺️ Roadmap

| # | Goal | Status |
|---|------|--------|
| 1 | Resume parser (PDF → profile, DE/EN) | ✅ done |
| 2 | Job search (Heilbronn Baden-Württemberg corridor) | ✅ done |
| 3 | Matching: profile ∩ job description | ✅ done |
| 4 | Interview prep (DE/EN questions & answers) | ✅ done |
| 5 | Cover letter (Anschreiben DE / cover letter EN) | ✅ done |
| 6 | Multi-tab app | 📋 planned |

An optional question-bank RAG would use the minimal `rag.py`.

See [`RESUME_JOBS.md`](RESUME_JOBS.md) for the full design, API notes, and out-of-scope items.
