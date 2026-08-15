"""Fetch and normalize intern postings from each company's public career board."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from html import unescape
from typing import Callable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from companies import Company
from http_client import RateLimitedSession

logger = logging.getLogger("intern_monitor")

INTERN_RE = re.compile(
    r"\b(intern|internship|internships|co-?op|co–op|university|campus|student)\b",
    re.I,
)
SWE_RE = re.compile(
    r"\b(software|engineer|engineering|swe|developer|programming|sde)\b",
    re.I,
)
STRIP_TAGS = re.compile(r"<[^>]+>")


@dataclass
class JobPosting:
    company: str
    title: str
    url: str
    posted_date: str
    location: str
    details: str
    job_id: str

    def fingerprint(self) -> str:
        return f"{self.company}|{self.job_id or self.url}"


def _text(value: object, limit: int = 400) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = ", ".join(_text(v, limit=0) for v in value if v)
    raw = unescape(STRIP_TAGS.sub(" ", str(value)))
    raw = re.sub(r"\s+", " ", raw).strip()
    if limit and len(raw) > limit:
        return raw[: limit - 1] + "…"
    return raw


def is_relevant(title: str, details: str = "") -> bool:
    """Keep intern/SWE-style roles. Title is required; details are a fallback."""
    blob = f"{title} {details}"
    return bool(INTERN_RE.search(blob) and SWE_RE.search(blob))


def _ok_json(resp, company: str) -> dict | list | None:
    if resp.status_code >= 400:
        logger.warning("%s HTTP %s for %s", company, resp.status_code, resp.url)
        return None
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "json" not in ctype and not resp.text.lstrip().startswith(("{", "[")):
        logger.warning("%s expected JSON from %s (got %s)", company, resp.url, ctype)
        return None
    try:
        return resp.json()
    except ValueError:
        logger.warning("%s JSON parse failed for %s", company, resp.url)
        return None


def fetch_greenhouse(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company.slug}/jobs?content=true"
    data = _ok_json(http.get(url), company.name)
    if not isinstance(data, dict):
        return []
    jobs = []
    for job in data.get("jobs") or []:
        jobs.append(
            JobPosting(
                company=company.name,
                title=_text(job.get("title"), 0),
                url=_text(job.get("absolute_url"), 0),
                posted_date=_text(job.get("first_published") or job.get("updated_at")),
                location=_text((job.get("location") or {}).get("name")),
                details=_text(job.get("content")),
                job_id=str(job.get("id") or ""),
            )
        )
    return jobs


def fetch_lever(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    url = f"https://api.lever.co/v0/postings/{company.slug}?mode=json"
    data = _ok_json(http.get(url), company.name)
    if not isinstance(data, list):
        return []
    jobs = []
    for job in data:
        cats = job.get("categories") or {}
        jobs.append(
            JobPosting(
                company=company.name,
                title=_text(job.get("text"), 0),
                url=_text(job.get("hostedUrl") or job.get("applyUrl"), 0),
                posted_date=_text(job.get("createdAt")),
                location=_text(cats.get("location") or job.get("country")),
                details=_text(job.get("descriptionPlain") or job.get("description")),
                job_id=str(job.get("id") or ""),
            )
        )
    return jobs


def fetch_ashby(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company.slug}"
    data = _ok_json(http.get(url), company.name)
    if not isinstance(data, dict):
        return []
    jobs = []
    for job in data.get("jobs") or []:
        jobs.append(
            JobPosting(
                company=company.name,
                title=_text(job.get("title"), 0),
                url=_text(job.get("jobUrl") or job.get("applyUrl"), 0),
                posted_date=_text(job.get("publishedAt") or job.get("updatedAt")),
                location=_text(job.get("location")),
                details=_text(
                    " | ".join(
                        p
                        for p in (
                            job.get("department"),
                            job.get("team"),
                            job.get("employmentType"),
                        )
                        if p
                    )
                ),
                job_id=str(job.get("id") or ""),
            )
        )
    return jobs


def fetch_workday(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    extra = company.extra
    tenant, dc, site = extra["tenant"], extra["dc"], extra["site"]
    endpoint = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    jobs: list[JobPosting] = []
    offset = 0
    limit = 20
    # Workday search is intern-focused so we don't pull thousands of full-time roles.
    body = {"appliedFacets": {}, "limit": limit, "offset": 0, "searchText": "intern"}
    while offset < 400:
        body["offset"] = offset
        resp = http.post(
            endpoint,
            json_body=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        data = _ok_json(resp, company.name)
        if not isinstance(data, dict):
            break
        postings = data.get("jobPostings") or []
        total = int(data.get("total") or 0)
        for job in postings:
            path = job.get("externalPath") or ""
            url = f"https://{tenant}.{dc}.myworkdayjobs.com/{site}{path}"
            jobs.append(
                JobPosting(
                    company=company.name,
                    title=_text(job.get("title"), 0),
                    url=url,
                    posted_date=_text(job.get("postedOn") or job.get("postedOnDisplay")),
                    location=_text(job.get("locationsText")),
                    details=_text(" ".join(job.get("bulletFields") or [])),
                    job_id=_text(path or job.get("title"), 0),
                )
            )
        offset += limit
        if offset >= total or not postings:
            break
    return jobs


def fetch_rippling(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    url = f"https://api.rippling.com/platform/api/ats/v1/board/{company.slug}/jobs"
    data = _ok_json(http.get(url), company.name)
    if not isinstance(data, list):
        return []
    jobs = []
    for job in data:
        loc = job.get("workLocation") or {}
        jobs.append(
            JobPosting(
                company=company.name,
                title=_text(job.get("name"), 0),
                url=_text(job.get("url"), 0),
                posted_date="",
                location=_text(loc.get("label") if isinstance(loc, dict) else loc),
                details=_text((job.get("department") or {}).get("label")),
                job_id=str(job.get("uuid") or ""),
            )
        )
    return jobs


def fetch_amazon(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    query = company.extra.get("query", "software engineer intern")
    jobs: list[JobPosting] = []
    offset = 0
    limit = 100
    while offset < 300:
        url = "https://www.amazon.jobs/en/search.json"
        params = {
            "base_query": query,
            "offset": offset,
            "result_limit": limit,
            "sort": "recent",
        }
        data = _ok_json(http.get(url, params=params), company.name)
        if not isinstance(data, dict):
            break
        batch = data.get("jobs") or []
        hits = int(data.get("hits") or 0)
        for job in batch:
            path = job.get("job_path") or ""
            jobs.append(
                JobPosting(
                    company=company.name,
                    title=_text(job.get("title"), 0),
                    url="https://www.amazon.jobs" + path if path.startswith("/") else path,
                    posted_date=_text(job.get("posted_date") or job.get("posted_date_readable")),
                    location=_text(job.get("normalized_location") or job.get("location")),
                    details=_text(job.get("description_short") or job.get("basic_qualifications")),
                    job_id=str(job.get("id_icims") or job.get("id") or path),
                )
            )
        offset += limit
        if offset >= hits or not batch:
            break
    return jobs


def fetch_eightfold(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    api = company.extra["api"]
    domain = company.extra.get("domain", "")
    query = company.extra.get("query", "intern")
    jobs: list[JobPosting] = []
    start = 0
    num = 20
    while start < 200:
        params = {
            "domain": domain,
            "start": start,
            "num": num,
            "query": query,
            "sort_by": "timestamp",
        }
        data = _ok_json(http.get(api, params=params), company.name)
        if not isinstance(data, dict):
            break
        positions = data.get("positions") or data.get("data", {}).get("positions") or []
        count = int(data.get("count") or data.get("totalCount") or 0)
        for job in positions:
            job_id = str(job.get("id") or job.get("positionID") or "")
            name = _text(job.get("name") or job.get("title"), 0)
            loc = job.get("location") or job.get("locations") or ""
            if isinstance(loc, list):
                loc = ", ".join(str(x) for x in loc)
            apply_url = (
                job.get("canonicalPositionUrl")
                or job.get("positionUrl")
                or f"{company.careers_url.rstrip('/')}/job/{job_id}"
            )
            jobs.append(
                JobPosting(
                    company=company.name,
                    title=name,
                    url=_text(apply_url, 0),
                    posted_date=_text(job.get("postedDate") or job.get("t_create")),
                    location=_text(loc),
                    details=_text(job.get("job_description") or job.get("department")),
                    job_id=job_id or name,
                )
            )
        start += num
        if not positions or (count and start >= count):
            break
    return jobs


def fetch_phenom(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    api = company.extra["api"]
    jobs: list[JobPosting] = []
    page = 1
    while page <= 10:
        data = _ok_json(http.get(api, params={"page": page, "limit": 50}), company.name)
        if not isinstance(data, dict):
            break
        batch = data.get("jobs") or []
        if not batch:
            break
        for wrap in batch:
            job = wrap.get("data") if isinstance(wrap, dict) and "data" in wrap else wrap
            if not isinstance(job, dict):
                continue
            slug = job.get("slug") or job.get("req_id") or ""
            title = _text(job.get("title"), 0)
            loc = job.get("location") or job.get("city") or ""
            url = job.get("apply_url") or job.get("url")
            if not url:
                url = f"https://www.github.careers/careers/{slug}" if slug else company.careers_url
            jobs.append(
                JobPosting(
                    company=company.name,
                    title=title,
                    url=_text(url, 0),
                    posted_date=_text(job.get("posted_date") or job.get("created_at")),
                    location=_text(loc),
                    details=_text(job.get("description")),
                    job_id=str(job.get("req_id") or slug or title),
                )
            )
        page += 1
        if len(batch) < 20:
            break
    return jobs


def fetch_microsoft(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    """Microsoft Eightfold search: /api/pcsx/search."""
    from datetime import datetime, timezone

    jobs: list[JobPosting] = []
    query = company.extra.get("query", "intern")
    location = company.extra.get("location", "")
    headers = {
        "Accept": "application/json",
        "Origin": "https://apply.careers.microsoft.com",
        "Referer": "https://apply.careers.microsoft.com/careers?sort_by=timestamp",
    }
    start = 0
    page_size = 10
    while start < 200:
        params = {
            "domain": "microsoft.com",
            "query": query,
            "start": start,
            "sort_by": "timestamp",
            "filter_include_remote": 1,
        }
        if location:
            params["location"] = location
        resp = http.get(
            "https://apply.careers.microsoft.com/api/pcsx/search",
            params=params,
            headers=headers,
        )
        payload = _ok_json(resp, company.name)
        if not isinstance(payload, dict):
            break
        inner = payload.get("data") or {}
        positions = inner.get("positions") or []
        count = int(inner.get("count") or 0)
        for job in positions:
            job_id = str(job.get("id") or job.get("atsJobId") or "")
            path = job.get("positionUrl") or f"/careers/job/{job_id}"
            posted = job.get("postedTs")
            posted_date = ""
            if posted:
                try:
                    posted_date = datetime.fromtimestamp(int(posted), timezone.utc).date().isoformat()
                except (TypeError, ValueError, OSError):
                    posted_date = str(posted)
            jobs.append(
                JobPosting(
                    company=company.name,
                    title=_text(job.get("name"), 0),
                    url=urljoin("https://apply.careers.microsoft.com", path),
                    posted_date=posted_date,
                    location=_text(job.get("locations") or job.get("standardizedLocations")),
                    details=_text(job.get("department") or job.get("workLocationOption")),
                    job_id=job_id,
                )
            )
        start += page_size
        if not positions or start >= count:
            break
    return jobs


def fetch_google(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    page = 1
    while page <= 8:
        url = (
            "https://www.google.com/about/careers/applications/jobs/results/"
            f"?location=United%20States&target_level=INTERN_AND_APPRENTICE"
            f"&sort_by=date&page={page}"
        )
        resp = http.get(url)
        if resp.status_code >= 400:
            logger.warning("Google HTTP %s page %s", resp.status_code, page)
            break
        found_this_page = 0
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a[href*='jobs/results/']"):
            href = a.get("href") or ""
            mid = re.search(r"jobs/results/(\d+)(?:-([^?\"'#]+))?", href)
            if not mid:
                continue
            job_id, slug = mid.group(1), mid.group(2) or ""
            title = _text(a.get_text(), 0)
            if not title or title.lower() in {"jobs", "job search", "sign in"}:
                h3 = a.find("h3")
                if not h3 and a.parent:
                    h3 = a.parent.find("h3")
                title = _text(h3.get_text() if h3 else "", 0)
            if not title and slug:
                title = slug.replace("-", " ").strip()
            if not title:
                continue
            abs_url = urljoin(
                "https://www.google.com/about/careers/applications/",
                href.split("?")[0],
            )
            jobs.append(
                JobPosting(
                    company=company.name,
                    title=title,
                    url=abs_url,
                    posted_date="",
                    location="United States",
                    details="Intern & Apprentice",
                    job_id=job_id,
                )
            )
            found_this_page += 1
        if found_this_page == 0:
            break
        page += 1
    uniq: dict[str, JobPosting] = {}
    for job in jobs:
        uniq[job.job_id] = job
    return list(uniq.values())


def fetch_apple(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    query = company.extra.get("query", "intern software")
    page = 1
    while page <= 10:
        payload = {
            "query": query,
            "locale": "en-us",
            "page": page,
            "filters": {"postingpostLocation": ["postLocation-USA"]},
        }
        resp = http.post(
            "https://jobs.apple.com/api/role/search",
            json_body=payload,
            headers={
                "Content-Type": "application/json",
                "Origin": "https://jobs.apple.com",
                "Referer": "https://jobs.apple.com/en-us/search",
                "Accept": "application/json",
            },
        )
        data = _ok_json(resp, company.name)
        if not isinstance(data, dict):
            break
        results = data.get("searchResults") or []
        total = int(data.get("totalRecords") or 0)
        for job in results:
            pos_id = str(job.get("positionId") or job.get("id") or "")
            locs = job.get("locations") or []
            loc_str = ", ".join(
                (loc.get("name") or loc.get("displayName") or "")
                for loc in locs
                if isinstance(loc, dict)
            )
            jobs.append(
                JobPosting(
                    company=company.name,
                    title=_text(job.get("postingTitle") or job.get("title"), 0),
                    url=f"https://jobs.apple.com/en-us/details/{pos_id}",
                    posted_date=_text(job.get("postingDate") or job.get("transformedPostingDate")),
                    location=_text(loc_str),
                    details=_text(job.get("jobSummary") or (job.get("team") or {}).get("teamName")),
                    job_id=pos_id,
                )
            )
        page += 1
        if not results or (total and len(jobs) >= total):
            break
    if jobs:
        return jobs

    html_url = (
        "https://jobs.apple.com/en-us/search?search="
        f"{query.replace(' ', '%20')}&sort=newest"
    )
    resp = http.get(html_url, headers={"Referer": "https://jobs.apple.com/"})
    if resp.status_code >= 400:
        return jobs
    html = resp.text
    titles = re.findall(r'\\"postingTitle\\":\\"([^\\]+)\\"', html) or re.findall(
        r'"postingTitle":"([^"]+)"', html
    )
    ids = re.findall(r'\\"positionId\\":\\"(\d+)\\"', html) or re.findall(
        r'"positionId":"(\d+)"', html
    )
    dates = re.findall(r'\\"postingDate\\":\\"([^\\]+)\\"', html) or re.findall(
        r'"postingDate":"([^"]+)"', html
    )
    for i, pos_id in enumerate(ids):
        title = titles[i] if i < len(titles) else ""
        if not title:
            continue
        jobs.append(
            JobPosting(
                company=company.name,
                title=_text(title, 0),
                url=f"https://jobs.apple.com/en-us/details/{pos_id}",
                posted_date=_text(dates[i] if i < len(dates) else ""),
                location="",
                details="",
                job_id=pos_id,
            )
        )
    return jobs


def fetch_meta(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    """Meta careers GraphQL: CareersJobSearchResultsV2DataQuery."""
    jobs: list[JobPosting] = []
    page_url = (
        company.careers_url
        or "https://www.metacareers.com/jobs?roles[0]=Internship&sort_by_new=true"
    )
    page = http.get(page_url)
    if page.status_code >= 400:
        logger.warning("Meta HTTP %s", page.status_code)
        return jobs
    lsd_m = re.search(r'\["LSD",\[\],\{"token":"([^"]+)"', page.text)
    if not lsd_m:
        logger.warning("Meta: no LSD token in careers HTML")
        return jobs
    lsd = lsd_m.group(1)
    doc_id = str(company.extra.get("doc_id") or "27129360303422352")
    search_input = {
        "q": None,
        "divisions": [],
        "offices": [],
        "roles": ["Internship"],
        "leadership_levels": [],
        "saved_jobs": [],
        "saved_searches": [],
        "sub_teams": [],
        "teams": [],
        "is_leadership": False,
        "is_remote_only": False,
        "sort_by_new": True,
        "page": 1,
    }
    variables = {
        "isLoggedIn": False,
        "viewasUserID": None,
        "search_input": search_input,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": page_url,
        "Origin": "https://www.metacareers.com",
        "X-FB-LSD": lsd,
        "X-FB-Friendly-Name": "CareersJobSearchResultsV2DataQuery",
        "Accept": "*/*",
    }
    payload = {
        "lsd": lsd,
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "CareersJobSearchResultsV2DataQuery",
        "server_timestamps": "true",
        "doc_id": doc_id,
        "variables": json.dumps(variables),
    }
    resp = http.post(
        "https://www.metacareers.com/api/graphql",
        form_data=payload,
        headers=headers,
    )
    data = _ok_json(resp, company.name)
    if not isinstance(data, dict):
        return jobs
    inner = (data.get("data") or {}).get("job_search_with_featured_jobs_v2") or {}
    listings = list(inner.get("all_jobs") or []) + list(inner.get("featured_jobs") or [])
    seen: set[str] = set()
    for job in listings:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("id") or "")
        title = _text(job.get("title"), 0)
        if not job_id or job_id in seen or not title:
            continue
        seen.add(job_id)
        loc = job.get("locations") or []
        teams = job.get("teams") or []
        sub = job.get("sub_teams") or []
        jobs.append(
            JobPosting(
                company=company.name,
                title=title,
                url=f"https://www.metacareers.com/jobs/{job_id}",
                posted_date="",
                location=_text(loc),
                details=_text(list(teams) + list(sub)),
                job_id=job_id,
            )
        )
    return jobs


def fetch_tesla(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    # Tesla uses Akamai bot checks. A real Safari window can pass them;
    # this script impersonates Safari TLS but may still get a challenge page.
    warm = http.get(company.careers_url or "https://www.tesla.com/careers/search/?type=intern&site=US")
    if "akamai" in warm.text.lower() and "sec-if-cpt-container" in warm.text:
        logger.warning(
            "Tesla returned an Akamai challenge page. "
            "The intern search works in Safari, but not from this script."
        )
        return jobs
    endpoints = [
        "https://www.tesla.com/cua-api/apps/careers/state",
        "https://www.tesla.com/cua-api/careers/search/?site=US&query=&department=0&type=3&offset=0&limit=100",
        "https://www.tesla.com/api/tesla/header/v1_1/careers",
    ]
    for url in endpoints:
        resp = http.get(url, headers={"Referer": company.careers_url, "Accept": "application/json"})
        data = _ok_json(resp, company.name)
        if data is None:
            continue
        listings = []
        if isinstance(data, dict):
            listings = (
                data.get("listings")
                or data.get("results")
                or (data.get("data") or {}).get("listings")
                or []
            )
            if not listings:
                for key in ("jobs", "items", "positions"):
                    if isinstance(data.get(key), list):
                        listings = data[key]
                        break
        elif isinstance(data, list):
            listings = data
        for job in listings:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or job.get("shortcode") or job.get("jobId") or "")
            title = _text(job.get("title") or job.get("name"), 0)
            loc = job.get("location") or job.get("city") or ""
            jobs.append(
                JobPosting(
                    company=company.name,
                    title=title,
                    url=f"https://www.tesla.com/careers/search/job/{job_id}" if job_id else company.careers_url,
                    posted_date=_text(job.get("postedDate") or job.get("created_at")),
                    location=_text(loc),
                    details=_text(job.get("description") or job.get("department")),
                    job_id=job_id or title,
                )
            )
        if jobs:
            break
    if not jobs:
        resp = http.get(company.careers_url)
        if resp.status_code < 400:
            jobs.extend(_jobs_from_html(company, resp.text, company.careers_url))
    return jobs


def fetch_tiktok(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    recruitment_ids = company.extra.get("recruitment_ids", ["202", "301"])
    offset = 0
    limit = 20
    payload = {
        "keyword": "software",
        "limit": limit,
        "offset": 0,
        "portal_type": 3,
        "portal_entrance": 1,
        "language": "en",
        "recruitment_id_list": recruitment_ids,
    }
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://lifeattiktok.com",
        "Referer": "https://lifeattiktok.com/search",
        "portal-channel": "campus",
        "portal-platform": "pc",
        "website-path": "tiktok",
    }
    endpoints = [
        "https://lifeattiktok.com/api/v1/search/job/posts",
        "https://jobs.bytedance.com/api/v1/search/job/posts",
        "https://job.tiktok.com/s/api/v1/search/job/posts",
    ]
    working = None
    while offset < 200:
        payload["offset"] = offset
        data = None
        for endpoint in ([working] if working else endpoints):
            if not endpoint:
                continue
            resp = http.post(endpoint, json_body=payload, headers=headers)
            if resp.status_code == 405:
                resp = http.get(
                    endpoint,
                    params={
                        "keyword": "software",
                        "limit": limit,
                        "offset": offset,
                        "recruitment_id_list": ",".join(recruitment_ids),
                    },
                    headers=headers,
                )
            parsed = _ok_json(resp, company.name)
            if isinstance(parsed, dict) and parsed.get("code") in (0, None, "0"):
                data = parsed
                working = endpoint
                break
        if not isinstance(data, dict):
            break
        inner = data.get("data") or data
        posts = inner.get("job_post_list") or inner.get("job_postings") or inner.get("list") or []
        count = int(inner.get("count") or inner.get("total") or 0)
        for job in posts:
            job_id = str(job.get("id") or job.get("job_id") or "")
            title = _text(job.get("title") or job.get("job_title"), 0)
            city = job.get("city_info") or job.get("city_list") or job.get("location")
            jobs.append(
                JobPosting(
                    company=company.name,
                    title=title,
                    url=f"https://lifeattiktok.com/position/{job_id}" if job_id else company.careers_url,
                    posted_date=_text(job.get("publish_time") or job.get("create_time")),
                    location=_text(city),
                    details=_text(job.get("job_category") or job.get("description")),
                    job_id=job_id or title,
                )
            )
        offset += limit
        if not posts or (count and offset >= count):
            break
    return jobs


def fetch_avature(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    page = 1
    while page <= 8:
        sep = "&" if "?" in company.careers_url else "?"
        url = f"{company.careers_url}{sep}page={page}"
        resp = http.get(url)
        if resp.status_code >= 400:
            break
        page_jobs = _jobs_from_html(company, resp.text, url)
        if not page_jobs:
            break
        jobs.extend(page_jobs)
        page += 1
    return jobs


def fetch_atlassian(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    url = "https://www.atlassian.com/endpoint/careers/listings"
    resp = http.get(url, headers={"Accept": "application/json", "Referer": company.careers_url})
    data = _ok_json(resp, company.name)
    if not isinstance(data, list):
        return []
    jobs: list[JobPosting] = []
    for job in data:
        if not isinstance(job, dict):
            continue
        portal = job.get("portalJobPost") or {}
        job_id = str(job.get("id") or portal.get("id") or "")
        apply_url = (
            job.get("applyUrl")
            or portal.get("portalUrl")
            or f"https://www.atlassian.com/company/careers/details/{job_id}"
        )
        jobs.append(
            JobPosting(
                company=company.name,
                title=_text(job.get("title"), 0),
                url=_text(apply_url, 0),
                posted_date=_text(portal.get("updatedDate")),
                location=_text(job.get("locations")),
                details=_text(job.get("category") or job.get("overview")),
                job_id=job_id,
            )
        )
    return jobs


def fetch_html(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    if "linkedin.com" in (company.careers_url or ""):
        logger.warning(
            "%s uses a LinkedIn company page, which cannot be scraped reliably. "
            "Add a Greenhouse/Ashby/careers URL in companies.py.",
            company.name,
        )
        return []
    resp = http.get(company.careers_url)
    if resp.status_code >= 400:
        logger.warning("%s HTML fetch HTTP %s", company.name, resp.status_code)
        return []
    return _jobs_from_html(company, resp.text, company.careers_url)


def _jobs_from_html(company: Company, html: str, page_url: str) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue
        blocks = payload if isinstance(payload, list) else [payload]
        for block in blocks:
            if not isinstance(block, dict):
                continue
            graph = block.get("@graph") if block.get("@type") != "JobPosting" else [block]
            if block.get("@type") == "JobPosting":
                graph = [block]
            for node in graph or []:
                if not isinstance(node, dict) or node.get("@type") != "JobPosting":
                    continue
                title = _text(node.get("title"), 0)
                url = _text(node.get("url"), 0) or page_url
                jobs.append(
                    JobPosting(
                        company=company.name,
                        title=title,
                        url=url,
                        posted_date=_text(node.get("datePosted")),
                        location=_text(
                            (node.get("jobLocation") or {}).get("address")
                            if isinstance(node.get("jobLocation"), dict)
                            else node.get("jobLocation")
                        ),
                        details=_text(node.get("description")),
                        job_id=url,
                    )
                )

    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        title = _text(a.get_text(), 0)
        if not title or len(title) < 8 or len(title) > 160:
            continue
        if not INTERN_RE.search(title):
            continue
        abs_url = urljoin(page_url, href)
        if abs_url.startswith("mailto:") or abs_url.startswith("javascript:"):
            continue
        jobs.append(
            JobPosting(
                company=company.name,
                title=title,
                url=abs_url,
                posted_date="",
                location="",
                details="",
                job_id=abs_url,
            )
        )

    uniq: dict[str, JobPosting] = {}
    for job in jobs:
        uniq[job.fingerprint()] = job
    return list(uniq.values())


def _direct_get(http: RateLimitedSession, url: str, headers: dict | None = None):
    """Same session, skip the global inter-company delay (used for sitemap fan-out)."""
    kwargs = {"timeout": 25, "headers": headers or {}, "allow_redirects": True}
    try:
        return http.session.get(url, impersonate="safari184", **kwargs)
    except TypeError:
        return http.session.get(url, **kwargs)


def fetch_workable(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    slug = company.slug
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"
    data = _ok_json(http.get(url), company.name)
    if not isinstance(data, dict):
        return []
    jobs = []
    for job in data.get("jobs") or []:
        loc = job.get("location") or {}
        if isinstance(loc, dict):
            loc = loc.get("location_str") or loc.get("city") or loc.get("country") or ""
        jobs.append(
            JobPosting(
                company=company.name,
                title=_text(job.get("title"), 0),
                url=_text(job.get("url") or job.get("shortlink") or job.get("application_url"), 0),
                posted_date=_text(job.get("published_on") or job.get("created_at")),
                location=_text(loc or job.get("country")),
                details=_text(job.get("department") or job.get("employment_type")),
                job_id=str(job.get("shortcode") or job.get("code") or job.get("title") or ""),
            )
        )
    return jobs


def fetch_jibe(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    """Oracle Jibe / CX talent sites such as careers.docusign.com."""
    api = company.extra.get("api") or urljoin(company.careers_url, "/api/jobs")
    query = company.extra.get("query", "intern")
    jobs: list[JobPosting] = []
    page = 1
    page_size = 50
    while page <= 8:
        params = {"pageSize": page_size, "page": page, "keyword": query}
        data = _ok_json(http.get(api, params=params), company.name)
        if not isinstance(data, dict):
            break
        batch = data.get("jobs") or []
        total = int(data.get("totalCount") or data.get("count") or 0)
        for wrap in batch:
            job = wrap.get("data") if isinstance(wrap, dict) and "data" in wrap else wrap
            if not isinstance(job, dict):
                continue
            slug = str(job.get("slug") or job.get("req_id") or "")
            title = _text(job.get("title"), 0)
            apply = job.get("apply_url") or ""
            job_base = company.extra.get("job_url_base", "").rstrip("/")
            url = f"{job_base}/{slug}" if job_base and slug else (apply or company.careers_url)
            jobs.append(
                JobPosting(
                    company=company.name,
                    title=title,
                    url=_text(url, 0),
                    posted_date=_text(job.get("posted_date") or job.get("create_date")),
                    location=_text(job.get("full_location") or job.get("city") or job.get("location_name")),
                    details=_text(job.get("category") or job.get("employment_type") or job.get("description")),
                    job_id=str(job.get("req_id") or slug or title),
                )
            )
        page += 1
        if not batch or (total and page_size * (page - 1) >= total):
            break
    return jobs


def fetch_tinder(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    """Tinder listings live on Webflow; the sitemap is the only complete index."""
    sitemap = http.get("https://www.lifeattinder.com/sitemap.xml")
    if sitemap.status_code >= 400:
        logger.warning("Tinder sitemap HTTP %s", sitemap.status_code)
        return []
    locs = re.findall(
        r"<loc>(https://(?:www\.)?lifeattinder\.com/positions/([^<]+))</loc>",
        sitemap.text,
    )
    by_id: dict[str, str] = {}
    for url, slug in locs:
        mid = re.match(
            r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
            slug,
            re.I,
        )
        if not mid:
            continue
        by_id.setdefault(mid.group(1), url)
    jobs: list[JobPosting] = []
    for job_id, url in by_id.items():
        time.sleep(0.12)
        resp = _direct_get(http, url)
        if resp.status_code >= 400:
            continue
        title_m = re.search(r"<h1[^>]*>(.*?)</h1>", resp.text, re.S | re.I)
        title = _text(unescape(re.sub(r"<[^>]+>", "", title_m.group(1))) if title_m else "", 0)
        if not title:
            continue
        loc_m = re.search(r"/positions/[0-9a-f-]+-(.+)$", url, re.I)
        jobs.append(
            JobPosting(
                company=company.name,
                title=title,
                url=url,
                posted_date="",
                location=_text(loc_m.group(1).replace("-", " ") if loc_m else ""),
                details="",
                job_id=job_id,
            )
        )
    return jobs


FETCHERS: dict[str, Callable[[RateLimitedSession, Company], list[JobPosting]]] = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
    "rippling": fetch_rippling,
    "amazon": fetch_amazon,
    "eightfold": fetch_eightfold,
    "phenom": fetch_phenom,
    "microsoft": fetch_microsoft,
    "google": fetch_google,
    "apple": fetch_apple,
    "meta": fetch_meta,
    "tesla": fetch_tesla,
    "tiktok": fetch_tiktok,
    "avature": fetch_avature,
    "atlassian": fetch_atlassian,
    "workable": fetch_workable,
    "jibe": fetch_jibe,
    "tinder": fetch_tinder,
    "html": fetch_html,
}


def check_company(http: RateLimitedSession, company: Company) -> list[JobPosting]:
    """Pull postings for one company and keep intern/SWE matches."""
    fetcher = FETCHERS.get(company.source)
    if not fetcher:
        logger.error("No fetcher for source=%s company=%s", company.source, company.name)
        return []
    try:
        raw = fetcher(http, company)
    except Exception:
        logger.exception("Failed to check %s (%s)", company.name, company.source)
        return []
    relevant = [job for job in raw if job.title and is_relevant(job.title, job.details)]
    logger.info(
        "%s: %s listings fetched, %s intern/SWE matches",
        company.name,
        len(raw),
        len(relevant),
    )
    return relevant
