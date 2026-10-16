"""Job search Streamlit page (future = tab 2 of the multi-tab app).

Run: .venv/bin/python -m streamlit run jobs_app.py
"""
import json
import sys

import streamlit as st
from dotenv import load_dotenv

sys.path.append(".")
from resume_jobs.jobs import get_job_details, search_corridor  # noqa: E402
from resume_jobs.store import save_jobs  # noqa: E402

load_dotenv()

st.set_page_config(page_title="JobPilot · Job Search", page_icon="🔎", layout="wide")
st.title("🔎 Job Search — Heilbronn · Stuttgart · Baden-Württemberg")
st.caption("JobPilot · Live listings from the Bundesagentur für Arbeit Jobsuche API (public, no key required).")

OFFER_OPTIONS = {
    "Full-time (ARBEIT)": 1,
    "Vocational training (AUSBILDUNG)": 4,
    "Internship / Trainee": 34,
}
# Remote is not an Angebotsart: the API's Homeoffice filter returns nothing, so
# it is handled as an extra nationwide keyword search (see search_corridor).
REMOTE_LABEL = "Remote / Homeoffice"
PUBLISHED_OPTIONS = {"Any time": None, "Last 7 days": 7, "Last 30 days": 30}

if "jobs" not in st.session_state:
    st.session_state.jobs = None

with st.form("search_form"):
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        keyword = st.text_input("Keyword / role", value="Data Engineer")
    with col2:
        selected_offers = st.multiselect(
            "Job types",
            list(OFFER_OPTIONS) + [REMOTE_LABEL],
            default=["Full-time (ARBEIT)", "Vocational training (AUSBILDUNG)",
                     "Internship / Trainee", REMOTE_LABEL],
        )
    with col3:
        radius = st.slider("Radius (km per city)", 10, 80, 45)

    published_label = st.selectbox("Published within", list(PUBLISHED_OPTIONS))
    submitted = st.form_submit_button("Search", type="primary")

if submitted:
    offer_types = tuple(OFFER_OPTIONS[l] for l in selected_offers if l in OFFER_OPTIONS) or (1,)
    remote = REMOTE_LABEL in selected_offers
    corridor = (("Heilbronn", radius), ("Stuttgart", max(10, radius - 10)), ("Baden-Württemberg", None))
    with st.spinner("Searching the corridor..."):
        try:
            st.session_state.jobs = search_corridor(
                keyword=keyword or None,
                corridor=corridor,
                remote=remote,
                offer_types=offer_types,
                published_within=PUBLISHED_OPTIONS[published_label],
                size=50,
            )
        except Exception as exc:  # report explicitly, never silent
            st.error(f"Search failed: {exc}")

jobs = st.session_state.jobs

if jobs is not None:
    st.success(f"{len(jobs)} unique jobs found")
    if jobs:
        table = [
            {
                "distance_km": job["distance_km"],
                "title": job["title"],
                "company": job["company"],
                "location": job["location"],
                "published": job["published"],
                "type": job["offer_type"],
            }
            for job in jobs
        ]
        st.dataframe(table, use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ Download results JSON",
            data=json.dumps(jobs, ensure_ascii=False, indent=2),
            file_name="jobs.json",
            mime="application/json",
        )
        if st.button("💾 Save to local data/"):
            st.success(f"Saved: {save_jobs(jobs, keyword=keyword or 'jobs')}")

        st.divider()
        st.subheader("Job details")
        labels = [f"{job['title']} — {job['company']}" for job in jobs]
        index = st.selectbox("Select a job", range(len(jobs)), format_func=lambda i: labels[i])
        job = jobs[index]

        st.markdown(f"**{job['title']}** @ {job['company']}")
        st.write(f"- Location: {job['location']} ({job['distance_km']} km)")
        st.write(f"- Offer type: {job['offer_type']} | Full-time: {job['full_time']}")
        st.write(f"- Salary info: {job['salary']} | Contract: {job['contract']}")
        if job.get("url"):
            st.markdown(f"- Posting: [{job['url']}]({job['url']})")

        if st.button("Load full description"):
            with st.spinner("Fetching details..."):
                try:
                    details = get_job_details(job["id"])
                    job.update(details)
                except Exception as exc:
                    st.error(f"Could not load details: {exc}")

        if job.get("description"):
            st.markdown("**Description (original, usually German)**")
            st.text_area("description", job["description"], height=300, label_visibility="collapsed")
