from datetime import date

from resume_jobs.experience import calculate_years_experience, experience_months
from resume_jobs.render import profile_block


def test_experience_is_calculated_from_dated_entries_and_deduplicates_overlap():
    entries = [
        {"start": "01/2020", "end": "12/2021"},
        {"start": "2021-06", "end": "heute"},
    ]
    assert experience_months(entries, date(2024, 1, 15)) == 49
    assert calculate_years_experience(entries, date(2024, 1, 15)) == 4.1


def test_unparseable_dates_do_not_inflate_experience():
    assert calculate_years_experience([{"start": "unknown", "end": "present"}]) == 0.0


def test_education_entries_do_not_count_as_work_experience():
    entries = [
        {"title": "Master of Computer Science", "company": "Universität Stuttgart",
         "start": "10/2018", "end": "09/2022"},
        {"title": "Junior Developer", "company": "ACME",
         "start": "01/2023", "end": "12/2023"},
    ]
    assert calculate_years_experience(entries) == 1.0


def test_profile_prompt_render_includes_industry():
    block = profile_block({
        "experience": [{
            "title": "Developer", "company": "ACME", "industry": "Software",
            "start": "2022", "end": "present", "highlights_en": [],
        }],
    })
    assert "Industry: Software" in block
