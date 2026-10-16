"""Offline tests for the Arbeitnow job source.

Uses a FakeSession so no network access is required. Shapes mirror the live
`/api/job-board-api` response.
"""
from resume_jobs.arbeitnow import BASE_URL, normalize_job, search


def raw_item(slug="data-engineer-berlin-1", title="Data Engineer", location="Berlin",
             remote=False, tags=None, job_types=None, description="<p>We use <b>data</b>.</p>"):
    return {
        "slug": slug,
        "company_name": "ACME GmbH",
        "title": title,
        "description": description,
        "remote": remote,
        "url": f"https://www.arbeitnow.com/jobs/companies/acme/{slug}",
        "tags": tags if tags is not None else ["Data Engineer"],
        "job_types": job_types if job_types is not None else ["berufserfahren"],
        "location": location,
        "created_at": "1767225600",  # 2026-01-01
    }


class FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, pages):
        # pages: {page_number: [items]}
        self.pages = pages
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        page = (params or {}).get("page", 1)
        self.calls.append({"url": url, "page": page})
        return FakeResponse({"data": self.pages.get(page, [])})


def test_normalize_maps_fields_and_namespaces_id():
    job = normalize_job(raw_item())
    assert job["source"] == "arbeitnow"
    assert job["id"] == "arbeitnow:data-engineer-berlin-1"
    assert job["title"] == "Data Engineer"
    assert job["company"] == "ACME GmbH"
    assert job["location"] == "Berlin"
    assert job["url"].endswith("data-engineer-berlin-1")
    assert job["published"] == "2026-01-01"
    assert job["description"] == "We use data."  # tags stripped, entity-free
    assert job["distance_km"] is None  # no coordinates from this source


def test_search_matches_title_and_tags_not_description():
    match = raw_item(slug="a", title="Senior Data Engineer", tags=["Data"])
    # 'data' only appears in the description -> must NOT match
    noise = raw_item(slug="b", title="Barista", tags=["Coffee"],
                     description="<p>Some data entry.</p>")
    session = FakeSession({1: [match, noise], 2: []})
    jobs = search("Data Engineer", http=session)
    assert [j["id"] for j in jobs] == ["arbeitnow:a"]
    assert session.calls[0]["url"] == BASE_URL


def test_search_remote_only_and_size_limit():
    items = [raw_item(slug=f"s{i}", remote=(i % 2 == 0)) for i in range(6)]
    session = FakeSession({1: items})
    jobs = search(max_pages=1, remote_only=True, size=2, http=session)
    assert len(jobs) == 2
    assert all(j["remote"] for j in jobs)


def test_search_filters_by_location_but_keeps_remote():
    heil = raw_item(slug="h", title="Data Engineer", location="Heilbronn")
    stgt = raw_item(slug="s", title="Data Engineer", location="Stuttgart")
    paris = raw_item(slug="p", title="Data Engineer", location="Paris")
    rem = raw_item(slug="r", title="Data Engineer", location="", remote=True)
    session = FakeSession({1: [heil, stgt, paris, rem]})
    jobs = search("Data Engineer", locations=["Heilbronn", "Stuttgart"], max_pages=1, http=session)
    assert {j["id"] for j in jobs} == {"arbeitnow:h", "arbeitnow:s", "arbeitnow:r"}


def test_search_stops_when_a_page_is_empty():
    session = FakeSession({1: [raw_item(slug="a")], 2: []})
    jobs = search(max_pages=5, http=session)
    assert len(jobs) == 1
    assert [c["page"] for c in session.calls] == [1, 2]  # page 2 empty -> stop
