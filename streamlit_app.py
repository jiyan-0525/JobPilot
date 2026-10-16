"""KarrierePilot — the whole flow in one Streamlit app.

Tabs: Resume → Jobs → Match → Interview → Cover letter.
Each step reuses the `resume_jobs` library; state is carried in session_state.

Run: .venv/bin/python -m streamlit run streamlit_app.py
"""
import json
import sys

import streamlit as st
from dotenv import load_dotenv

sys.path.append(".")
from resume_jobs.cover_letter import write_cover_letter  # noqa: E402
from resume_jobs.interview import prepare_interview  # noqa: E402
from resume_jobs.jobs import search_corridor  # noqa: E402
from resume_jobs.match import rank_jobs  # noqa: E402
from resume_jobs.render import profile_block  # noqa: E402
from resume_jobs.resume import extract_text, parse_profile  # noqa: E402
from resume_jobs.store import save_jobs, save_profile  # noqa: E402

load_dotenv()

st.set_page_config(page_title="KarrierePilot", page_icon="🧭", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.6rem; }
      .kp-hero {
        background: linear-gradient(120deg, #1e3a8a 0%, #2563eb 55%, #0ea5e9 100%);
        padding: 1.5rem 1.7rem; border-radius: 18px; color: #fff;
        box-shadow: 0 10px 28px rgba(37, 99, 235, .28); margin-bottom: 1.1rem;
      }
      .kp-hero h1 { margin: 0; font-size: 1.75rem; font-weight: 800; color: #fff; }
      .kp-hero p  { margin: .4rem 0 0; opacity: .93; font-size: .95rem; }
      .kp-chip {
        display: inline-block; background: rgba(255,255,255,.16);
        border: 1px solid rgba(255,255,255,.28); padding: 2px 11px;
        border-radius: 999px; font-size: .78rem; margin: .55rem .35rem 0 0;
      }
      .stButton > button { border-radius: 10px; font-weight: 600; }
      .stDownloadButton > button { border-radius: 10px; }
      .stTabs [data-baseweb="tab-list"] { gap: 6px; }
      .stTabs [data-baseweb="tab"] {
        border-radius: 10px 10px 0 0; padding: 7px 16px; font-weight: 600;
      }
      [data-testid="stMetricValue"] { font-weight: 800; color: #1e3a8a; }
      .kp-muted { color: #64748b; font-size: .85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="kp-hero">
      <h1>🧭 KarrierePilot</h1>
      <p>Resume → Jobs → Match → Interview → Cover letter &nbsp;·&nbsp;
         Heilbronn Baden-Württemberg &nbsp;·&nbsp; German + English</p>
      <span class="kp-chip">1 Parse</span><span class="kp-chip">2 Search</span>
      <span class="kp-chip">3 Match</span><span class="kp-chip">4 Interview</span>
      <span class="kp-chip">5 Cover letter</span>
    </div>
    """,
    unsafe_allow_html=True,
)

OFFER_OPTIONS = {"Full-time (ARBEIT)": 1, "Vocational (AUSBILDUNG)": 4, "Internship/Trainee": 34}
PUBLISHED_OPTIONS = {"Any time": None, "Last 7 days": 7, "Last 30 days": 30}

for key in ("profile", "jobs", "ranked", "job", "interview_md", "cover_de", "cover_en"):
    st.session_state.setdefault(key, None)

tabs = st.tabs(["1 · Resume", "2 · Jobs", "3 · Match", "4 · Interview", "5 · Cover letter"])
tab_resume, tab_jobs, tab_match, tab_interview, tab_cover = tabs

# ---- 1 · Resume -----------------------------------------------------------
with tab_resume:
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

        with st.container(border=True):
            st.markdown(f"**Target roles**  \n{roles}")
            st.markdown(f"**Skills**  \n{', '.join(skills) or '—'}")
            st.markdown(f"**Languages**  \n{languages}")

        with st.expander("Full profile"):
            st.text(profile_block(profile))

        c1, c2 = st.columns(2)
        c1.download_button("⬇️ profile.json", json.dumps(profile, ensure_ascii=False, indent=2),
                           "profile.json", "application/json", use_container_width=True)
        if c2.button("💾 Save profile", use_container_width=True):
            st.success(f"Saved: {save_profile(profile)}")

# ---- 2 · Jobs -------------------------------------------------------------
with tab_jobs:
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
    offers = col2.multiselect("Job types", list(OFFER_OPTIONS), default=list(OFFER_OPTIONS))
    radius = col3.slider("Radius (km per city)", 10, 80, 45)
    published = st.selectbox("Published within", list(PUBLISHED_OPTIONS))

    if st.button("Search jobs", type="primary"):
        offer_types = tuple(OFFER_OPTIONS[o] for o in offers) or (1,)
        corridor = (("Heilbronn", radius), ("Stuttgart", max(10, radius - 10)))
        with st.spinner("Searching the corridor…"):
            try:
                st.session_state.jobs = search_corridor(
                    keyword=keyword or None, corridor=corridor, offer_types=offer_types,
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
                    "km": st.column_config.NumberColumn("km", format="%d km"),
                    "open": st.column_config.LinkColumn("open", display_text="Open ↗"),
                })

            c1, c2 = st.columns(2)
            c1.download_button("⬇️ jobs.json", json.dumps(jobs, ensure_ascii=False, indent=2),
                               "jobs.json", "application/json", use_container_width=True)
            if c2.button("💾 Save jobs", use_container_width=True):
                st.success(f"Saved: {save_jobs(jobs, keyword=keyword or 'jobs')}")

# ---- 3 · Match ------------------------------------------------------------
with tab_match:
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

            labels = [f"{r['score']:.0f} · {r['job']['title']} @ {r['job']['company']}" for r in ranked]
            idx = st.selectbox("Pick the target job", range(len(ranked)), format_func=lambda i: labels[i])
            st.session_state.job = ranked[idx]["job"]
            st.success(f"Target job selected — **{st.session_state.job['title']}** "
                       f"@ {st.session_state.job['company']} (tabs 4 & 5)")
            if st.session_state.job["url"]:
                st.link_button("🔗 Open job posting", st.session_state.job["url"])

# ---- 4 · Interview --------------------------------------------------------
with tab_interview:
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
