"""JobPilot — the whole flow in one Streamlit app.

Tabs: Resume → Jobs → Match → Interview → Cover letter.
Each step reuses the `resume_jobs` library; state is carried in session_state.

Run: .venv/bin/python -m streamlit run streamlit_app.py
"""
import html
import json
import sys

import streamlit as st
from dotenv import load_dotenv

sys.path.append(".")
from resume_jobs.cover_letter import write_cover_letter  # noqa: E402
from resume_jobs.interview import prepare_interview  # noqa: E402
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
      /* ---- layout -------------------------------------------------------- */
      .block-container { padding-top: 1.3rem; padding-bottom: 3rem; max-width: 1180px; }
      #MainMenu, header [data-testid="stToolbar"], footer { visibility: hidden; }

      /* ---- hero ---------------------------------------------------------- */
      .kp-hero {
        position: relative; overflow: hidden; color: #fff;
        background:
          radial-gradient(1100px 380px at 88% -30%, rgba(56,189,248,.55), transparent 60%),
          linear-gradient(120deg, #0b2a6b 0%, #1e40af 42%, #2563eb 72%, #0ea5e9 100%);
        padding: 2rem 2.1rem 1.7rem; border-radius: 22px;
        box-shadow: 0 22px 45px -18px rgba(37,99,235,.65);
        margin-bottom: 1.4rem;
      }
      .kp-hero h1 {
        margin: 0; font-size: 2.05rem; font-weight: 800; color: #fff;
        letter-spacing: -.02em;
      }
      .kp-hero p { margin: .5rem 0 0; opacity: .95; font-size: 1rem; }
      .kp-chips { margin-top: .95rem; }
      .kp-chip {
        display: inline-flex; align-items: center; gap: .35rem;
        background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.32);
        padding: 4px 13px; border-radius: 999px; font-size: .78rem; font-weight: 600;
        margin: 0 .4rem .4rem 0;
      }

      /* ---- section header ------------------------------------------------ */
      .kp-section { display: flex; align-items: center; gap: .65rem; margin: .3rem 0 1rem; }
      .kp-section .bar {
        width: 5px; height: 1.35rem; border-radius: 999px;
        background: linear-gradient(#2563eb, #0ea5e9);
      }
      .kp-section h2 { margin: 0; font-size: 1.22rem; font-weight: 700; color: #0f172a; }

      /* ---- cards --------------------------------------------------------- */
      .kp-card {
        background: #fff; border: 1px solid #e6ebf4; border-radius: 16px;
        padding: 1rem 1.15rem; height: 100%;
        box-shadow: 0 8px 22px -16px rgba(15,23,42,.45);
      }
      .kp-card .k {
        color: #64748b; font-size: .74rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: .07em;
      }
      .kp-card .s { color: #475569; font-size: .88rem; margin-top: .15rem; line-height: 1.5; }

      /* ---- widgets ------------------------------------------------------- */
      .stButton > button, .stDownloadButton > button, .stLinkButton > a {
        border-radius: 12px; font-weight: 600;
        transition: transform .08s ease, box-shadow .15s ease;
      }
      .stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 22px -12px rgba(37,99,235,.75);
      }
      div[data-testid="stMetric"] {
        background: #fff; border: 1px solid #e6ebf4; border-radius: 16px;
        padding: .8rem 1rem; box-shadow: 0 8px 22px -18px rgba(15,23,42,.5);
      }
      [data-testid="stMetricValue"] { font-weight: 800; color: #1e3a8a; }
      [data-testid="stMetricLabel"] { color: #64748b; font-weight: 600; }

      div[data-testid="stFileUploader"] section,
      div[data-testid="stExpander"] details {
        border-radius: 14px; border-color: #e6ebf4;
      }

      /* ---- tabs ---------------------------------------------------------- */
      .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #e6ebf4; }
      .stTabs [data-baseweb="tab"] {
        border-radius: 12px 12px 0 0; padding: 8px 18px; font-weight: 600; color: #475569;
      }
      .stTabs [aria-selected="true"] { color: #1d4ed8; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="kp-hero">
      <h1>🧭 JobPilot</h1>
      <p>Resume → Jobs → Match → Interview → Cover letter &nbsp;·&nbsp;
         Heilbronn · Stuttgart · Baden-Württemberg · Remote &nbsp;·&nbsp; German + English</p>
      <div class="kp-chips">
        <span class="kp-chip">1 · Parse</span><span class="kp-chip">2 · Search</span>
        <span class="kp-chip">3 · Match</span><span class="kp-chip">4 · Interview</span>
        <span class="kp-chip">5 · Cover letter</span>
      </div>
    </div>
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

for key in ("profile", "jobs", "ranked", "job", "interview_md", "cover_de", "cover_en"):
    st.session_state.setdefault(key, None)

tabs = st.tabs(["1 · Resume", "2 · Jobs", "3 · Match", "4 · Interview", "5 · Cover letter"])
tab_resume, tab_jobs, tab_match, tab_interview, tab_cover = tabs

# ---- 1 · Resume -----------------------------------------------------------
with tab_resume:
    section("📄", "Resume")
    uploaded = st.file_uploader("Upload resume PDF", type=["pdf"])
    pasted = st.text_area("…or paste the resume text", height=130)

    text = ""
    if uploaded is not None:
        text = extract_text(uploaded)
        if not text:
            st.error("No text extracted — likely a scanned PDF (OCR unsupported).")
    elif pasted.strip():
        text = pasted.strip()

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
    radius = col3.slider("Radius (km per city)", 10, 80, 45)
    published = st.selectbox("Published within", list(PUBLISHED_OPTIONS))

    if st.button("Search jobs", type="primary"):
        offer_types = tuple(OFFER_OPTIONS[o] for o in offers if o in OFFER_OPTIONS) or (1,)
        remote = REMOTE_LABEL in offers
        corridor = ((HOME_POSTAL_CODE, radius), ("Stuttgart", max(10, radius - 10)), ("Baden-Württemberg", None))
        with st.spinner("Searching the corridor…"):
            try:
                st.session_state.jobs = search_corridor(
                    keyword=keyword or None, corridor=corridor, remote=remote, offer_types=offer_types,
                    published_within=PUBLISHED_OPTIONS[published], size=50)
                st.session_state.ranked = None
                st.session_state.job = None
            except Exception as exc:
                st.error(f"Search failed: {exc}")

    jobs = st.session_state.jobs
    if jobs is not None:
        st.success(f"{len(jobs)} jobs found")
        if jobs:
            distances = [j["distance_km"] for j in jobs if isinstance(j["distance_km"], (int, float))]
            m1, m2, m3 = st.columns(3)
            m1.metric("Jobs", len(jobs))
            m2.metric("Closest", f"{min(distances)} km" if distances else "—")
            m3.metric("Cities", len({j["location"] for j in jobs if j["location"]}))

            st.dataframe(
                [{"km": j["distance_km"], "title": j["title"], "company": j["company"],
                  "location": j["location"], "type": j["offer_type"], "open": j["url"]} for j in jobs],
                use_container_width=True, hide_index=True,
                column_config={
                    "km": st.column_config.NumberColumn("km from home", format="%.1f km"),
                    "open": st.column_config.LinkColumn("open", display_text="Open ↗"),
                })

            c1, c2 = st.columns(2)
            c1.download_button("⬇️ jobs.json", json.dumps(jobs, ensure_ascii=False, indent=2),
                               "jobs.json", "application/json", use_container_width=True)
            if c2.button("💾 Save jobs", use_container_width=True):
                st.success(f"Saved: {save_jobs(jobs, keyword=keyword or 'jobs')}")

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
                    st.session_state.ranked = rank_jobs(st.session_state.profile, st.session_state.jobs, top_n=8)
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
                use_container_width=True, hide_index=True,
                column_config={
                    "score": st.column_config.ProgressColumn(
                        "score", min_value=0, max_value=100, format="%d"),
                    "open": st.column_config.LinkColumn("open", display_text="Open ↗"),
                })

        # Pick from every fetched job: the shortlist is just the top of the list,
        # so a job the ranking skipped is still selectable.
        scores = {r["job_id"]: r["score"] for r in (ranked or [])}
        ordered = ([r["job"] for r in (ranked or [])]
                   + [j for j in st.session_state.jobs if j["id"] not in scores])
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
