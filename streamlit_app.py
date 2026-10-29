"""JobPilot — the whole flow in one Streamlit app.

Tabs: Resume → Jobs → Match (incl. Fit check) → Interview → Cover letter.
Each step reuses the `resume_jobs` library; state is carried in session_state.

Run: .venv/bin/python -m streamlit run streamlit_app.py
"""
import html
import json
import sys
from urllib.parse import quote

import streamlit as st
from dotenv import load_dotenv

sys.path.append(".")
from resume_jobs.cover_letter import (  # noqa: E402
    write_cover_letter,
    write_cover_letter_from_jd,
)
from resume_jobs.interview import prepare_interview  # noqa: E402
from resume_jobs.jd_fit import analyze_fit, learning_plan_markdown  # noqa: E402
from resume_jobs.jobs import HOME_POSTAL_CODE, search_corridor  # noqa: E402
from resume_jobs.match import rank_jobs  # noqa: E402
from resume_jobs.render import profile_block  # noqa: E402
from resume_jobs.resume import extract_text, parse_profile  # noqa: E402
from resume_jobs.store import save_jobs, save_profile  # noqa: E402

load_dotenv()

st.set_page_config(page_title="JobPilot", page_icon="🧭", layout="wide")

st.markdown(
    """
    <style>
      /* ---- palette ------------------------------------------------------- */
      :root {
        --kp-bg: #0b1220;
        --kp-surface: rgba(148,163,184,.06);
        --kp-surface-2: rgba(148,163,184,.10);
        --kp-border: rgba(148,163,184,.18);
        --kp-accent: #38bdf8;
        --kp-accent-2: #818cf8;
        --kp-text: #e2e8f0;
        --kp-muted: #94a3b8;
      }

      /* ---- layout -------------------------------------------------------- */
      .stApp {
        background:
          radial-gradient(900px 520px at 102% -12%, rgba(56,189,248,.12), transparent 58%),
          radial-gradient(760px 520px at -8% 6%, rgba(129,140,248,.12), transparent 55%),
          var(--kp-bg);
      }
      .block-container { padding: 1.4rem 2rem 3rem; max-width: 100%; }
      #MainMenu, header [data-testid="stToolbar"], footer { visibility: hidden; }

      /* ---- hero ---------------------------------------------------------- */
      .kp-hero {
        position: relative; overflow: hidden; color: #fff;
        background:
          radial-gradient(1100px 400px at 88% -30%, rgba(56,189,248,.50), transparent 62%),
          linear-gradient(120deg, #0b1a3a 0%, #1e2a78 40%, #4338ca 72%, #0ea5e9 100%);
        padding: 2.05rem 2.15rem 1.85rem; border-radius: 24px;
        border: 1px solid rgba(148,197,255,.24);
        box-shadow:
          0 34px 70px -34px rgba(56,189,248,.55),
          inset 0 1px 0 rgba(255,255,255,.16);
        margin-bottom: 1.5rem;
      }
      .kp-hero::after {
        content: ""; position: absolute; right: -70px; top: -70px;
        width: 240px; height: 240px; border-radius: 50%;
        background: radial-gradient(circle, rgba(125,211,252,.42), transparent 68%);
        filter: blur(4px); pointer-events: none;
      }
      .kp-hero h1 {
        margin: 0; font-size: 2.6rem; font-weight: 800; color: #fff;
        letter-spacing: -.02em; text-shadow: 0 2px 18px rgba(8,20,45,.55);
      }
      .kp-hero p { margin: .55rem 0 0; opacity: .95; font-size: 1.25rem; color: #dbeafe; }
      .kp-flag { height: 1em; vertical-align: -0.12em; border-radius: 2px; }

      /* ---- section header ------------------------------------------------ */
      .kp-section { display: flex; align-items: center; gap: .7rem; margin: .3rem 0 1.05rem; }
      .kp-section .bar {
        width: 5px; height: 1.4rem; border-radius: 999px;
        background: linear-gradient(var(--kp-accent-2), var(--kp-accent));
        box-shadow: 0 0 16px rgba(56,189,248,.7);
      }
      .kp-section h2 { margin: 0; font-size: 1.24rem; font-weight: 700; color: var(--kp-text); }

      /* ---- cards --------------------------------------------------------- */
      .kp-card {
        background: var(--kp-surface); border: 1px solid var(--kp-border); border-radius: 16px;
        padding: 1rem 1.15rem; height: 100%;
        backdrop-filter: blur(10px);
        box-shadow: 0 12px 32px -24px rgba(0,0,0,.9);
      }
      .kp-card .k {
        color: var(--kp-muted); font-size: .74rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: .07em;
      }
      .kp-card .s { color: #cbd5e1; font-size: .88rem; margin-top: .15rem; line-height: 1.55; }

      /* ---- widgets ------------------------------------------------------- */
      .stButton > button, .stDownloadButton > button, .stLinkButton > a {
        border-radius: 12px; font-weight: 600; color: var(--kp-text);
        background: var(--kp-surface-2); border: 1px solid var(--kp-border);
        transition: transform .08s ease, box-shadow .15s ease, border-color .15s ease;
      }
      .stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {
        transform: translateY(-1px); border-color: var(--kp-accent);
        box-shadow: 0 12px 28px -14px rgba(56,189,248,.65);
      }
      .stButton > button[kind="primary"] {
        background: linear-gradient(120deg, #2563eb, #0ea5e9); border: none; color: #fff;
        box-shadow: 0 14px 30px -16px rgba(56,189,248,.85);
      }
      div[data-testid="stMetric"] {
        background: var(--kp-surface); border: 1px solid var(--kp-border); border-radius: 16px;
        padding: .8rem 1rem; backdrop-filter: blur(10px);
        box-shadow: 0 12px 30px -26px rgba(0,0,0,.9);
      }
      [data-testid="stMetricValue"] { font-weight: 800; font-size: 1.5rem; color: #7dd3fc; }
      [data-testid="stMetricLabel"] { color: var(--kp-muted); font-weight: 600; }

      div[data-testid="stFileUploader"] section,
      div[data-testid="stExpander"] details,
      div[data-testid="stDataFrame"] {
        border-radius: 14px; border: 1px solid var(--kp-border);
        background: var(--kp-surface);
      }
      div[data-testid="stTextArea"] textarea, div[data-testid="stTextInput"] input,
      div[data-baseweb="select"] > div {
        border-radius: 10px; border-color: var(--kp-border);
        background: rgba(148,163,184,.06);
      }

      /* ---- tabs (pill style) --------------------------------------------- */
      .stTabs [data-baseweb="tab-list"] {
        gap: 10px; border-bottom: none; flex-wrap: wrap;
      }
      .stTabs [data-baseweb="tab-highlight"],
      .stTabs [data-baseweb="tab-border"] { display: none; }
      .stTabs [data-baseweb="tab"] {
        border-radius: 999px; padding: 6px 20px;
        background: var(--kp-surface-2); border: 1px solid var(--kp-border); color: var(--kp-muted);
      }
      .stTabs [data-baseweb="tab"]:hover { border-color: var(--kp-accent); }
      .stTabs [data-baseweb="tab"] p,
      .stTabs [data-baseweb="tab"] div,
      .stTabs [data-baseweb="tab"] span {
        font-size: 1.15rem !important; font-weight: 800 !important; color: inherit !important;
      }
      .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: var(--kp-accent); border-color: var(--kp-accent); color: #04121f;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

def section(icon, title):
    """A small accented heading shown at the top of each tab."""
    st.markdown(
        f'<div class="kp-section"><span class="bar"></span><h2>{icon} {title}</h2></div>',
        unsafe_allow_html=True,
    )

OFFER_OPTIONS = {"Full-time (ARBEIT)": 1, "Vocational (AUSBILDUNG)": 4, "Internship/Trainee": 34}
# Remote is not an Angebotsart: the API's Homeoffice filter returns nothing, so
# it is handled as an extra nationwide keyword search (see search_corridor).
REMOTE_LABEL = "Remote / Homeoffice"
PUBLISHED_OPTIONS = {"Any time": None, "Last 7 days": 7, "Last 30 days": 30}


def glassdoor_url(keyword: str) -> str:
    """Deep link into Glassdoor's German job search (no public API available)."""
    return "https://www.glassdoor.de/Job/jobs.htm?sc.keyword=" + quote(keyword or "")


def filter_jobs_for_profile(profile: dict, jobs: list[dict]) -> list[dict]:
    """Hide clearly senior jobs for profiles without verified senior evidence."""
    career_level = profile.get("career_level") or {}
    evidence = " ".join(str(item).lower() for item in career_level.get("evidence") or [])
    try:
        confidence = float(career_level.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    verified = (
        str(career_level.get("level") or "").lower() == "senior"
        and confidence >= 0.85
        and any(term in evidence for term in (
            "architecture", "architect", "end-to-end", "end to end", "mentoring",
            "mentor", "team lead", "leadership", "architektur", "teamleitung",
        ))
    )
    if verified:
        return jobs
    markers = (
        "senior", "lead", "principal", "staff engineer", "teamleitung",
        "team lead", "technical lead", "tech lead", "fachliche führung",
        "fachliche leitung", "leitung eines teams",
    )
    return [
        job for job in jobs
        if not any(marker in " ".join(
            str(job.get(key) or "").lower()
            for key in ("title", "occupation", "description")
        ) for marker in markers)
    ]


def job_as_description(job: dict) -> str:
    """Render a ranked job as job-description text for the fit check."""
    header = " @ ".join(
        part for part in (job.get("title") or "", job.get("company") or "") if part
    )
    parts = [
        header,
        f"Location: {job['location']}" if job.get("location") else "",
        f"Offer type: {job['offer_type']}" if job.get("offer_type") else "",
        str(job.get("description") or ""),
    ]
    return "\n".join(part for part in parts if part).strip()


def render_fit_check():
    """Fit-check a ranked job or a pasted job description and show the learning plan."""
    section("🧩", "Fit check")
    if st.session_state.profile:
        st.caption(f"Comparing against **{st.session_state.profile['name'] or 'your profile'}** "
                   "— pick a job from the score list or paste a job posting.")
    else:
        st.caption("Upload a PDF or paste resume text above, then analyze it before generating a cover letter.")

    ranked = st.session_state.ranked or []
    selected_job = None
    paste_option = "— Paste a different job description —"
    if ranked:
        # Reset the picker when a new ranking changes the number of entries.
        if st.session_state.get("fit_choice_count") != len(ranked):
            st.session_state.fit_job_choice = 0
            st.session_state.fit_choice_count = len(ranked)
        labels = [
            f"{r.get('score', 0):.0f} · {r['job'].get('title', '')} @ {r['job'].get('company', '')}"
            for r in ranked
        ]
        choice = st.selectbox(
            "Choose a job from the score list",
            options=list(range(len(ranked) + 1)),
            format_func=lambda i: labels[i] if i < len(ranked) else paste_option,
            key="fit_job_choice",
        )
        if choice < len(ranked):
            selected_job = ranked[choice]["job"]

    if selected_job:
        jd_text = job_as_description(selected_job)
        st.caption(f"Analyzing **{selected_job.get('title', '')}** @ "
                   f"**{selected_job.get('company', '')}** — "
                   f"{selected_job.get('location') or 'location not stated'}")
        with st.expander("Job description"):
            st.write(jd_text or "No description available for this job.")
        if not jd_text:
            st.warning("This job has no description yet — pick another job or paste the description instead.")
    else:
        with st.expander("Job description — paste job description here", expanded=not ranked):
            jd_text = st.text_area(
                "Job description",
                height=200,
                key="jd_text",
                placeholder="Paste the full job advertisement here…",
                label_visibility="collapsed",
            )

    target_key = str(selected_job.get("id")) if selected_job else "paste"
    if st.session_state.profile:
        if st.button("Analyze fit for this job", type="primary", disabled=not jd_text.strip()):
            with st.spinner("Comparing the job description with your resume…"):
                try:
                    st.session_state.fit_result = analyze_fit(st.session_state.profile, jd_text)
                    st.session_state.fit_target = target_key
                except Exception as exc:
                    st.error(f"Fit check failed: {exc}")
    elif jd_text.strip():
        st.info("Analyze a PDF or pasted resume text above before generating a cover letter.")

    if jd_text.strip() and st.session_state.profile:
        st.markdown("##### ✉️ Generate a cover letter from this job description")
        jd_cover_c1, jd_cover_c2 = st.columns(2)
        if jd_cover_c1.button("🇩🇪 Generate Anschreiben", type="primary", use_container_width=True):
            with st.spinner("Schreibe Anschreiben…"):
                try:
                    st.session_state.jd_cover_de = write_cover_letter_from_jd(
                        st.session_state.profile or {},
                        jd_text,
                        language="de",
                    )
                except Exception as exc:
                    st.error(f"Cover letter generation failed: {exc}")
        if jd_cover_c2.button("🇬🇧 Generate cover letter", type="primary", use_container_width=True):
            with st.spinner("Writing cover letter…"):
                try:
                    st.session_state.jd_cover_en = write_cover_letter_from_jd(
                        st.session_state.profile or {},
                        jd_text,
                        language="en",
                    )
                except Exception as exc:
                    st.error(f"Cover letter generation failed: {exc}")

        if st.session_state.jd_cover_de:
            st.markdown(st.session_state.jd_cover_de)
            st.download_button(
                "⬇️ anschreiben_from_jd_de.md",
                st.session_state.jd_cover_de,
                "anschreiben_from_jd_de.md",
                "text/markdown",
            )
        if st.session_state.jd_cover_en:
            st.markdown(st.session_state.jd_cover_en)
            st.download_button(
                "⬇️ cover_letter_from_jd_en.md",
                st.session_state.jd_cover_en,
                "cover_letter_from_jd_en.md",
                "text/markdown",
            )
    elif jd_text.strip():
        st.info("Cover letter generation needs your resume so it can be grounded in your experience.")

    fit = st.session_state.fit_result
    if fit and st.session_state.profile and st.session_state.fit_target == target_key:
        m1, m2 = st.columns(2)
        m1.metric("Fit score", f"{fit['score']:.0f} / 100")
        m2.metric("Verdict", fit["verdict"] or "—")

        c1, c2 = st.columns(2)
        c1.markdown(
            '<div class="kp-card">'
            f'<div class="k">Matched ({len(fit["matched_skills"])})</div>'
            f'<div class="s">{html.escape(", ".join(fit["matched_skills"]) or "—")}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        c2.markdown(
            '<div class="kp-card">'
            f'<div class="k">Missing ({len(fit["missing_skills"])})</div>'
            f'<div class="s">{html.escape(", ".join(fit["missing_skills"]) or "—")}</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        if fit["reason_de"]:
            st.markdown(f"**🇩🇪 {fit['reason_de']}**")
        if fit["reason_en"]:
            st.markdown(f"**🇬🇧 {fit['reason_en']}**")

        plan = fit.get("learning_plan") or []
        if plan:
            st.markdown("##### 📚 Learning plan — what to learn before applying")
            st.dataframe(
                [{"priority": step["priority"], "learn": step["skill"],
                  "why it matters": step["why"], "how to learn": step["how"],
                  "effort": step["effort"]} for step in plan],
                width="stretch", hide_index=True,
            )
            st.download_button(
                "⬇️ learning_plan.md",
                learning_plan_markdown(fit),
                "learning_plan.md", "text/markdown")


for key in (
    "profile", "jobs", "ranked", "job", "interview_md", "cover_de", "cover_en",
    "fit_result", "fit_target", "jd_cover_de", "jd_cover_en",
):
    st.session_state.setdefault(key, None)

st.markdown(
    """
    <div class="kp-hero">
      <h1>🧭 JobPilot</h1>
      <p>📄 Resume → 🔎 Jobs → 🎯 Match → 🗣️ Interview → ✉️ Cover letter &nbsp;·&nbsp;
         <img class="kp-flag" src="https://flagcdn.com/w40/de.png" alt="DE"> +
         <img class="kp-flag" src="https://flagcdn.com/w40/gb.png" alt="GB"></p>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(["📄 1 · Resume", "🔎 2 · Jobs", "🎯 3 · Match",
                "🗣️ 4 · Interview", "✉️ 5 · Cover letter"])
tab_resume, tab_jobs, tab_match, tab_interview, tab_cover = tabs

# ---- 1 · Resume -----------------------------------------------------------
with tab_resume:
    section("📄", "Resume")
    uploaded = st.file_uploader("Upload resume PDF", type=["pdf"])
    with st.expander("PDF not available? Paste resume text instead"):
        pasted_resume = st.text_area(
            "Resume text",
            height=160,
            key="pasted_resume",
            placeholder="Paste your resume text here…",
        )

    text = ""
    if uploaded is not None:
        text = extract_text(uploaded)
        if not text:
            st.error("No text extracted — likely a scanned PDF (OCR unsupported).")
    elif pasted_resume.strip():
        text = pasted_resume.strip()

    if st.button("Analyze resume", type="primary", disabled=not text):
        with st.spinner("Extracting profile…"):
            try:
                st.session_state.profile = parse_profile(text)
            except Exception as exc:
                st.error(f"Parsing failed: {exc}")

    profile = st.session_state.profile
    if profile:
        st.success(f"Profile ready — {profile['name'] or 'unnamed'}")
        roles = ", ".join(profile["target_roles"]) or "—"
        skills = profile["skills"]["technical"]
        languages = ", ".join(f"{x['language']} ({x['level']})" for x in profile["languages"]) or "—"

        m1, m2, m3 = st.columns(3)
        m1.metric("Experience", f"{profile['years_experience']:g} yrs")
        m2.metric("Technical skills", len(skills))
        m3.metric("Languages", len(profile["languages"]))

        st.markdown(
            f'<div class="kp-card">'
            f'<div class="k">Target roles</div><div class="s">{html.escape(roles)}</div>'
            f'<div class="k" style="margin-top:.75rem">Industry experience</div>'
            f'<div class="s">{html.escape(", ".join(sorted({e.get("industry") for e in profile.get("experience", []) if e.get("industry")}) or ["Not stated"]))}</div>'
            f'<div class="k" style="margin-top:.75rem">Skills</div>'
            f'<div class="s">{html.escape(", ".join(skills) or "—")}</div>'
            f'<div class="k" style="margin-top:.75rem">Languages</div>'
            f'<div class="s">{html.escape(languages)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Full profile"):
            st.text(profile_block(profile))

        c1, c2 = st.columns(2)
        c1.download_button("⬇️ profile.json", json.dumps(profile, ensure_ascii=False, indent=2),
                           "profile.json", "application/json", use_container_width=True)
        if c2.button("💾 Save profile", use_container_width=True):
            st.success(f"Saved: {save_profile(profile)}")

# ---- 2 · Jobs -------------------------------------------------------------
with tab_jobs:
    section("🔎", "Jobs")
    roles = (st.session_state.profile or {}).get("target_roles") or []

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        if roles:  # search keyword comes from the profile's real roles
            picked = st.selectbox("Role (from your profile)", list(roles) + ["Custom keyword…"])
            keyword = (st.text_input("Custom keyword", placeholder="e.g. Data Engineer")
                       if picked == "Custom keyword…" else picked)
        else:
            keyword = st.text_input("Keyword / role", value="Data Engineer")
            st.caption("Tip: run tab 1 first — the search then uses your profile's target roles.")
    offers = col2.multiselect("Job types", list(OFFER_OPTIONS) + [REMOTE_LABEL],
                              default=list(OFFER_OPTIONS) + [REMOTE_LABEL])
    radius = col3.slider("Radius (km per city)", 10, 300, 45)
    published = st.selectbox("Published within", list(PUBLISHED_OPTIONS))
    include_arbeitnow = st.checkbox("Also search Arbeitnow (second source, no key)", value=True)

    search_col, gl_col = st.columns([3, 1])
    search_clicked = search_col.button("Search jobs", type="primary", use_container_width=True)
    gl_col.link_button("🌐 Glassdoor", glassdoor_url(keyword), use_container_width=True)

    if search_clicked:
        offer_types = tuple(OFFER_OPTIONS[o] for o in offers if o in OFFER_OPTIONS) or (1,)
        remote = REMOTE_LABEL in offers
        corridor = ((HOME_POSTAL_CODE, radius), ("Stuttgart", radius))
        with st.spinner("Searching the corridor…"):
            try:
                st.session_state.jobs = search_corridor(
                    keyword=keyword or None, corridor=corridor, remote=remote, offer_types=offer_types,
                    published_within=PUBLISHED_OPTIONS[published], size=50,
                    include_arbeitnow=include_arbeitnow, max_distance_km=radius)
                st.session_state.ranked = None
                st.session_state.job = None
            except Exception as exc:
                st.error(f"Search failed: {exc}")

    jobs = st.session_state.jobs
    if jobs is not None:
        visible_jobs = filter_jobs_for_profile(st.session_state.profile or {}, jobs)
        st.success(f"{len(visible_jobs)} suitable jobs found")
        if visible_jobs:
            distances = [j["distance_km"] for j in visible_jobs if isinstance(j["distance_km"], (int, float))]
            m1, m2, m3 = st.columns(3)
            m1.metric("Jobs", len(visible_jobs))
            m2.metric("Closest", f"{min(distances)} km" if distances else "—")
            m3.metric("Cities", len({j["location"] for j in visible_jobs if j["location"]}))

            st.dataframe(
                [{"source": j.get("source", ""), "km": j["distance_km"], "title": j["title"],
                  "company": j["company"], "location": j["location"], "type": j["offer_type"],
                  "open": j["url"]} for j in visible_jobs],
                width="stretch", hide_index=True,
                column_config={
                    "km": st.column_config.NumberColumn("km from home", format="%.1f km"),
                    "open": st.column_config.LinkColumn("open", display_text="Open ↗"),
                })

            c1, c2 = st.columns(2)
            c1.download_button("⬇️ jobs.json", json.dumps(visible_jobs, ensure_ascii=False, indent=2),
                               "jobs.json", "application/json", use_container_width=True)
            if c2.button("💾 Save jobs", use_container_width=True):
                st.success(f"Saved: {save_jobs(visible_jobs, keyword=keyword or 'jobs')}")

# ---- 3 · Match ------------------------------------------------------------
with tab_match:
    section("🎯", "Match")
    if not st.session_state.profile or not st.session_state.jobs:
        st.info("Run tabs 1 (resume) and 2 (jobs) first.")
    else:
        st.caption("Ranks the fetched jobs against the profile — fetches full descriptions for the shortlist.")
        if st.button("Rank jobs", type="primary"):
            with st.spinner("Scoring…"):
                try:
                    st.session_state.ranked = rank_jobs(
                        st.session_state.profile,
                        filter_jobs_for_profile(st.session_state.profile, st.session_state.jobs),
                        top_n=8,
                    )
                except Exception as exc:
                    st.error(f"Ranking failed: {exc}")

        ranked = st.session_state.ranked
        if ranked:
            best = ranked[0]
            m1, m2 = st.columns(2)
            m1.metric("Best fit", f"{best['score']:.0f} / 100")
            m2.metric("Shortlist", len(ranked))

            st.dataframe(
                [{"score": r["score"], "title": r["job"]["title"], "company": r["job"]["company"],
                  "reason (EN)": r["reason_en"], "open": r["job"]["url"]} for r in ranked],
                width="stretch", hide_index=True,
                column_config={
                    "score": st.column_config.ProgressColumn(
                        "score", min_value=0, max_value=100, format="%d"),
                    "open": st.column_config.LinkColumn("open", display_text="Open ↗"),
                })

        render_fit_check()

        # Pick from every fetched job: the shortlist is just the top of the list,
        # so a job the ranking skipped is still selectable.
        scores = {r["job_id"]: r["score"] for r in (ranked or [])}
        visible_jobs = filter_jobs_for_profile(st.session_state.profile, st.session_state.jobs)
        ordered = ([r["job"] for r in (ranked or [])]
                   + [j for j in visible_jobs if j["id"] not in scores])
        labels = [
            f"{scores[j['id']]:.0f} · {j['title']} @ {j['company']} — {j['location'] or '—'}"
            if j["id"] in scores else
            f"{j['title']} @ {j['company']} — {j['location'] or '—'}"
            for j in ordered
        ]
        idx = st.selectbox("Pick the target job", range(len(ordered)), format_func=lambda i: labels[i])
        st.session_state.job = ordered[idx]
        st.success(f"Target job selected — **{st.session_state.job['title']}** "
                   f"@ {st.session_state.job['company']} (tabs 4 & 5)")
        if st.session_state.job["url"]:
            st.link_button("🔗 Open job posting", st.session_state.job["url"])

# ---- 4 · Interview --------------------------------------------------------
with tab_interview:
    section("🗣️", "Interview")
    if not st.session_state.profile or not st.session_state.job:
        st.info("Complete tabs 1–3 to pick a target job.")
    else:
        job = st.session_state.job
        st.markdown(f"**Target:** {job['title']} @ {job['company']}")
        if job["url"]:
            st.link_button("🔗 Open job posting", job["url"])
        if st.button("Generate interview prep", type="primary"):
            with st.spinner("Preparing interview material (DE + EN)…"):
                try:
                    st.session_state.interview_md = prepare_interview(st.session_state.profile, job)
                except Exception as exc:
                    st.error(f"Failed: {exc}")
        if st.session_state.interview_md:
            st.markdown(st.session_state.interview_md)
            st.download_button("⬇️ interview_materials.md", st.session_state.interview_md,
                               "interview_materials.md", "text/markdown")

# ---- 5 · Cover letter -----------------------------------------------------
with tab_cover:
    section("✉️", "Cover letter")
    if not st.session_state.profile or not st.session_state.job:
        st.info("Complete tabs 1–3 to pick a target job.")
    else:
        job = st.session_state.job
        st.markdown(f"**Target:** {job['title']} @ {job['company']}")
        if job["url"]:
            st.link_button("🔗 Open job posting", job["url"])

        c1, c2 = st.columns(2)
        if c1.button("🇩🇪 Deutsch (Anschreiben)", type="primary", use_container_width=True):
            with st.spinner("Schreibe Anschreiben…"):
                try:
                    st.session_state.cover_de = write_cover_letter(
                        st.session_state.profile, job, language="de")
                except Exception as exc:
                    st.error(f"Failed: {exc}")
        if c2.button("🇬🇧 English (Cover letter)", type="primary", use_container_width=True):
            with st.spinner("Writing cover letter…"):
                try:
                    st.session_state.cover_en = write_cover_letter(
                        st.session_state.profile, job, language="en")
                except Exception as exc:
                    st.error(f"Failed: {exc}")

        if st.session_state.cover_de:
            st.markdown(st.session_state.cover_de)
            st.download_button("⬇️ anschreiben_de.md", st.session_state.cover_de,
                               "anschreiben_de.md", "text/markdown")
        if st.session_state.cover_en:
            st.markdown(st.session_state.cover_en)
            st.download_button("⬇️ cover_letter_en.md", st.session_state.cover_en,
                               "cover_letter_en.md", "text/markdown")
