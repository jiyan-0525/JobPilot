# JobPilot — Design & Roadmap

Resume → Jobs → Interview for the **Heilbronn Baden-Württemberg** corridor, bilingual (German + English),
built on Groq + GPT-OSS 120B.

---

## Pipeline

| Layer | What it does | Implementation | Status |
|---|---|---|---|
| 1 Parse | PDF → text → structured profile | `resume_jobs/resume.py` (LLM function calling) | ✅ done |
| 2 Job search | profile → real job postings | `resume_jobs/jobs.py` (Bundesagentur für Arbeit Jobsuche API) | ✅ done |
| 3 Matching | score/rank profile ∩ job description | `resume_jobs/match.py` (keyword prefilter + LLM ranking) | ✅ done |
| 4 Interview prep | generate DE/EN interview questions for a job | `resume_jobs/interview.py` (LLM step; question-bank RAG optional) | ✅ done |
| 5 Fit check | paste a JD → fit score + gaps → DE/EN learning plan | `resume_jobs/match.py` (`score_job`) + `resume_jobs/learning_plan.py` | ✅ done |

Steps 3 and 4 are built on `resume_jobs/step.py`, a small **role + task + expected_output +
context** step framing: `run_step` for prose, `run_step_tool` for structured output.

> Key design decision: **the resume does not go into RAG.** A resume is a single document that fits
> in context, so it is fed straight to the LLM. RAG's real target is the fetched job-description
> corpus and the interview question bank.

The former calculator / weather demo tools (old `agent.py`, `app.py`) have been removed. The shared
Groq client now lives in `resume_jobs/llm.py`.

---

## Layout

```
resume_app.py           # Streamlit: resume → profile       (tab 1)
jobs_app.py             # Streamlit: job search corridor     (tab 2)
resume_jobs/
├── llm.py              # shared Groq client (lazy init)
├── schema.py           # profile JSON schema + normalization (no third-party deps)
├── resume.py           # extract_text(pdf) / parse_profile(text, client=None)
├── jobs.py             # Arbeitsagentur client (search + details + corridor)
├── step.py             # step framing: run_step / run_step_tool
├── render.py           # profile_block / job_block for prompts
├── match.py            # rank_jobs (step 3)
├── interview.py        # prepare_interview (step 4)
├── cover_letter.py     # write_cover_letter (per language: de / en)
├── learning_plan.py    # build_learning_plan (fit check → DE/EN study plan)
└── store.py            # JSON persistence: save_profile / save_jobs
rag.py                  # minimal RAG (question bank)
tests/test_resume.py    # offline tests
tests/test_jobs.py      # offline tests
data/                   # generated artifacts (gitignored)
```

---

## Step 1 — Resume parser

Upload a PDF resume → extract text → LLM structuring → normalized profile JSON (German + English).

### Profile schema

Factual fields stay language-neutral; free text reused for interviews / cover letters is emitted in
both German and English.

```json
{
  "source_language": "de",
  "name": "",
  "contact": {"email": "", "phone": "", "location": "", "linkedin": "", "github": ""},
  "languages": [{"language": "Deutsch", "level": "B2"}],
  "target_roles": ["Data Engineer"],
  "years_experience": 5,
  "skills": {"technical": [], "tools": [], "soft": []},
  "experience": [
    {"title": "", "company": "", "location": "", "start": "", "end": "",
     "highlights_de": [], "highlights_en": []}
  ],
  "education": [{"degree": "", "institution": "", "start": "", "end": ""}],
  "certifications": [],
  "mobility": "",
  "availability": "",
  "summary_de": "",
  "summary_en": "",
  "raw_text": "(extracted source text, kept for debugging and re-extraction)"
}
```

### Implementation notes

- **Extraction**: `resume_jobs/llm.py:get_client()` (Groq, `openai/gpt-oss-120b`). An `emit_profile`
  function schema is forced via `tool_choice` for a stable structure.
- **Testable**: `parse_profile(text, client=None)` accepts an injected client; tests pass a
  `FakeClient` and run **offline**.
- **Never silent**: a clearly empty extraction raises `ValueError` (shown by the UI); otherwise
  `normalize_profile` coerces any missing or garbled field to a safe default.
- **German details**: the prompt preserves original date text (`03/2021`, `seit 2020`, `heute`),
  detects `source_language`, and emits `summary_de` + `summary_en`.

---

## Step 2 — Job search

Live listings via the **Bundesagentur für Arbeit Jobsuche API** (Germany's largest job database,
public key, no registration). Verified against the live API (2026-10).

### API ground truth

| | Endpoint | Notes |
|---|---|---|
| Search | `GET /pc/v6/jobs` | response list is **`ergebnisliste`** (not `stellenangebote` in the old docs) |
| Details | `GET /pc/v4/jobdetails/{base64(referenznummer)}` | returns `stellenangebotsBeschreibung` (the full body) |
| Auth | header `X-API-Key: jobboerse-jobsuche` | public static key |
| v3 details | `GET /pc/v3/jobdetails/...` | **gone (403)** — use v4 |

- Search results carry **no description**, so details are a separate call per job (N+1). `enrich_jobs`
  fetches only a limited, cached subset.
- Multi-value filters are semicolon-separated and really do union:
  `angebotsart=1;4;34` → 55 + 0 + 3 = **58** results (ARBEIT + AUSBILDUNG + PRAKTIKUM/Trainee).
- `wo=Heilbronn&umkreis=50` switches the search to `UMKREISSUCHE` (radius); `umkreis=0` is a plain
  place search.
- v6 item shape (used by `normalize_job`): `stellenangebotsTitel`, `firma`, `hauptberuf`,
  `stellenlokationen[].{adresse{ort,plz,region,strasse,hausnummer}, breite, laenge}`,
  `referenznummer`, `entfernung`, `stellenangebotsart`, `arbeitszeitVollzeit`, `verguetungsangabe`,
  `vertragsdauer`, `datumErsteVeroeffentlichung`, `eintrittszeitraum`.
  (Older docs showed `refnr` / `koordinaten` — the live schema differs.)

### Corridor search

`CORRIDOR = (("Heilbronn", 45), ("Stuttgart", 35))` — two radius searches, merged and **deduped by
`referenznummer`**, keeping the smallest reported distance. Job types default to
`(1, 4, 34)` = ARBEIT + AUSBILDUNG + PRAKTIKUM/Trainee.

### Normalized job dict

```json
{
  "source": "arbeitsagentur", "id": "10001-1003252000-S",
  "title": "", "company": "", "location": "", "postal_code": "", "region": "", "street": "",
  "lat": null, "lon": null, "distance_km": 41,
  "published": "", "entry": "", "offer_type": "ARBEIT", "full_time": true,
  "salary": "", "contract": "", "occupation": "",
  "url": "https://www.arbeitsagentur.de/jobsuche/jobdetail/<id>",
  "description": ""
}
```

### Implementation notes

- HTTP client is injectable (`http=...`), so tests use a `FakeSession` and run **offline**.
- `_get` retries with linear backoff; `enrich_jobs` pauses between detail calls to stay polite.
- Public page links are built from the `referenznummer` (v6 results carry no `externeUrl`).

---

## Steps 3 & 4 — matching and interview prep

Both use the step framing from `step.py` (a system prompt from `role`, a user prompt of
`context` + `task` + `expected_output`) as plain OpenAI SDK calls — `run_step` for prose,
`run_step_tool` for structured output.

### Step 3 — `match.py`

```python
from resume_jobs.match import rank_jobs
ranked = rank_jobs(profile, jobs, top_n=8)   # enrich=True fetches the shortlist's descriptions
# -> [{"job_id", "score", "matched_skills", "missing_skills", "reason_de", "reason_en", "job"}, ...]
```

- `prefilter()` scores jobs by keyword overlap (offline, no LLM) and keeps the top `top_n`.
- `enrich_jobs()` then fetches full descriptions **only** for the shortlist (details are one request
  per job).
- one forced-tool call ranks them, bilingual reasons (DE/EN).
- Gotcha found live: the prompt must show each job's **id**, or the model returns a title string
  instead of `job_id`. `render.job_block()` now emits `Job id: …`, and `rank_jobs` still has a
  title-substring fallback.

### Step 4 — `interview.py`

```python
from resume_jobs.interview import prepare_interview
markdown = prepare_interview(profile, job)             # bilingual DE + EN
markdown = prepare_interview(profile, job, question_bank=gather_question_bank(query))
```

- Returns Markdown with `## Deutsch` and `## English`, each containing questions + answer outlines,
  a gap analysis, and questions to ask — grounded strictly in the resume (no-fabrication guard is in
  `step.NO_FABRICATION`).
- `question_bank` is an optional hook: `gather_question_bank()` uses `rag.py` when a question-bank
  folder exists, and returns `[]` otherwise (the German question bank corpus is still TBD).

### Cover letter — `cover_letter.py`

```python
from resume_jobs.cover_letter import write_cover_letter
write_cover_letter(profile, job, language="de")   # '## Deutsch (Anschreiben)'
write_cover_letter(profile, job, language="en")   # '## English (Cover letter)'
```

One LLM step **per language** — German and English are generated separately, so each can be
regenerated on its own. Each is grounded strictly in the resume (greeting/sign-off, opening,
2-3 evidenced strengths matching the job, motivation, closing).

### Fit check — `match.score_job` + `learning_plan.py`

The tab after Cover letter in the multi-tab app (`streamlit_app.py`): resume upload/paste + pasted JD.
`score_job(profile, job)` fit-checks one posting — it reuses
`rank_jobs` on a single job (a `SINGLE_JOB_MAX_DESCRIPTION` budget keeps the full JD in context)
and returns `{job_id, score, matched_skills, missing_skills, reason_de, reason_en}`. Those
`missing_skills` then feed `build_learning_plan(profile, job, gaps=...)`, one LLM step producing a
bilingual (DE/EN) study plan: prioritised gaps plus ordered, time-boxed learning steps.

## Usage

```bash
.venv/bin/python -m pip install -r requirements.txt

# Tab 1 — resume parser
.venv/bin/python -m streamlit run resume_app.py
# Tab 2 — job search
.venv/bin/python -m streamlit run jobs_app.py

# CLI: live search across the corridor
.venv/bin/python -m resume_jobs.jobs

# Tests (offline, no GROQ_API_KEY needed)
.venv/bin/python -m pytest tests/ -q
```

`.env` needs `GROQ_API_KEY` (used by the parsing step; job search and PDF extraction need no key).

---

## Known limitations

- Multi-column PDFs may be extracted in the wrong reading order; scanned PDFs (no text layer) are
  unsupported — OCR is out of scope.
- Job descriptions are usually **German only**; bilingual *generation* comes in step 4.
- The API exposes no reliable salary field (`verguetungsangabe` is often `KEINE_ANGABEN`).

---

## Next steps

5. **UI**: add matching, interview, and cover letter to the Streamlit app (tabs: Upload / Jobs /
   Match / Interview / Cover letter) — they are library functions with offline tests today.
6. **Question bank (optional)**: a German question-bank corpus, wired into `gather_question_bank()`
   → `prepare_interview`; retrieval uses `rag.py`.

## Explicitly out of scope

- Scraping StepStone / Indeed / LinkedIn (blocks + ToS violations).
- OCR for scanned documents.
- Reusing the Chinese embedding model (`bge-small-zh-v1.5`) for German retrieval — a multilingual
  model is required if the question-bank RAG is built.
- Multi-agent frameworks (CrewAI / AutoGen). The pipeline is linear orchestration, not agent
  collaboration; a framework would add cost and nondeterminism without improving the result.
