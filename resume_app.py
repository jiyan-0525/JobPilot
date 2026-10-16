"""Resume parser Streamlit page (future = tab 1 of the multi-tab app).

Run: .venv/bin/python -m streamlit run resume_app.py
"""
import json
import sys

import streamlit as st
from dotenv import load_dotenv

sys.path.append(".")
from resume_jobs import extract_text, parse_profile  # noqa: E402
from resume_jobs.store import save_profile  # noqa: E402

load_dotenv()

st.set_page_config(page_title="KarrierePilot · Resume Parser", page_icon="📄", layout="wide")
st.title("📄 Resume Parser")
st.caption("KarrierePilot · Upload a PDF resume → extract text → LLM-structured profile (German + English)")

if "profile" not in st.session_state:
    st.session_state.profile = None

uploaded = st.file_uploader("Upload resume PDF", type=["pdf"])

if uploaded is not None:
    text = extract_text(uploaded)
    if not text:
        st.error("No text extracted. The file may be a scan (no text layer); OCR is not supported yet.")
    else:
        with st.expander(f"📃 Extracted text ({len(text)} chars)", expanded=False):
            st.text(text[:3000] + ("\n..." if len(text) > 3000 else ""))

        if st.button("Analyze", type="primary"):
            with st.spinner("LLM is extracting the structured profile..."):
                try:
                    st.session_state.profile = parse_profile(text)
                except Exception as exc:  # report explicitly, never silent
                    st.error(f"Parsing failed: {exc}")

profile = st.session_state.profile

if profile:
    st.success("Done")
    st.subheader(profile.get("name") or "(name not detected)")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Contact**")
        contact = profile.get("contact") or {}
        for key, value in contact.items():
            if value:
                st.write(f"- {key}: {value}")
        st.markdown("**Languages**")
        for item in profile.get("languages") or []:
            st.write(f"- {item['language']}: {item['level']}")
        if profile.get("mobility"):
            st.markdown("**Mobility**")
            st.write(profile["mobility"])
        if profile.get("availability"):
            st.markdown("**Availability**")
            st.write(profile["availability"])

    with col2:
        st.markdown("**Target roles**")
        for role in profile.get("target_roles") or []:
            st.write(f"- {role}")
        years = profile.get("years_experience") or 0
        st.write(f"- Experience: about {years:g} years")
        skills = profile.get("skills") or {}
        for label, key in (("Technical", "technical"), ("Tools", "tools"), ("Soft skills", "soft")):
            if skills.get(key):
                st.markdown(f"**{label}**")
                st.write(" · ".join(skills[key]))

    st.markdown("**Summary**")
    lang = st.radio("Language", ["DE", "EN"], horizontal=True, label_visibility="collapsed")
    st.info(profile.get("summary_de") if lang == "DE" else profile.get("summary_en"))

    st.markdown("**Work experience**")
    for exp in profile.get("experience") or []:
        header = "{} — {} ({})".format(
            exp["title"], exp["company"], f"{exp['start']}–{exp['end']}"
        )
        st.markdown(f"**{header}**")
        highlights = exp["highlights_de"] if lang == "DE" else exp["highlights_en"]
        for point in highlights:
            st.write(f"- {point}")

    st.markdown("**Education**")
    for edu in profile.get("education") or []:
        line = "{} — {} ({})".format(
            edu["degree"], edu["institution"], f"{edu['start']}–{edu['end']}"
        )
        st.write(f"- {line}")

    if profile.get("certifications"):
        st.markdown("**Certifications**")
        for cert in profile["certifications"]:
            st.write(f"- {cert}")

    st.download_button(
        "⬇️ Download profile JSON",
        data=json.dumps(profile, ensure_ascii=False, indent=2),
        file_name="profile.json",
        mime="application/json",
    )
    if st.button("💾 Save to local data/"):
        st.success(f"Saved: {save_profile(profile)}")
