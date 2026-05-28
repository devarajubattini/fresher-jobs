import os
import re
import hashlib
from datetime import date, datetime, timezone
from dotenv import load_dotenv
from langchain_core.tools import tool
from jobspy import scrape_jobs
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_supabase: Client | None = None


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


# ---------------------------------------------------------------------------
# Constants from PROJECT.md
# ---------------------------------------------------------------------------

GAP_KEYWORDS = [
    "gap", "career break", "returnship", "return to work",
    "career gap", "break in career", "re-entry", "relaunch",
    "gap candidates", "gap year", "career pause",
]

SKILLS_LIST = [
    "SQL", "Python", "Excel", "Power BI", "Tableau", "Looker",
    "Google Analytics", "Data Studio", "MS Excel", "pivot tables",
    "VLOOKUP", "ETL", "data cleaning", "data visualization",
    "dashboards", "reporting", "MySQL", "PostgreSQL",
]

REMOTE_KEYWORDS = ["remote", "work from home", "wfh", "fully remote"]
HYBRID_KEYWORDS = ["hybrid", "2 days office", "3 days office", "flexible"]
WALKIN_KEYWORDS = ["walk-in", "walkin", "walk in interview", "direct interview"]

# Regex patterns for experience extraction
_EXP_RANGE_RE = re.compile(r"(\d+)\s*[-–to]+\s*(\d+)\s*(?:years?|yrs?)", re.IGNORECASE)
_EXP_PLUS_RE = re.compile(r"(\d+)\+\s*(?:years?|yrs?)", re.IGNORECASE)
_EXP_MIN_RE = re.compile(r"(?:minimum|min\.?|at\s*least)\s*(\d+)\s*(?:years?|yrs?)", re.IGNORECASE)
_EXP_SINGLE_RE = re.compile(r"(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job_id(title: str, company: str, location: str) -> str:
    raw = f"{title}{company}{location}".lower().strip()
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _parse_experience(description: str) -> tuple[int | None, int | None]:
    """Return (experience_min, experience_max) parsed from description text."""
    if not description:
        return None, None

    m = _EXP_RANGE_RE.search(description)
    if m:
        return int(m.group(1)), int(m.group(2))

    m = _EXP_PLUS_RE.search(description)
    if m:
        val = int(m.group(1))
        return val, val + 2  # e.g. "3+" → 3–5

    m = _EXP_MIN_RE.search(description)
    if m:
        val = int(m.group(1))
        return val, val + 2

    m = _EXP_SINGLE_RE.search(description)
    if m:
        val = int(m.group(1))
        return val, val

    return None, None


def _is_gap_friendly(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    return any(kw.lower() in text for kw in GAP_KEYWORDS)


def _classify_job_type(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if any(kw in text for kw in REMOTE_KEYWORDS):
        return "remote"
    if any(kw in text for kw in HYBRID_KEYWORDS):
        return "hybrid"
    if any(kw in text for kw in WALKIN_KEYWORDS):
        return "walkin"
    return "fulltime"


def _extract_skills(description: str) -> list[str]:
    if not description:
        return []
    text = description.lower()
    return [skill for skill in SKILLS_LIST if skill.lower() in text]


def _scrape(search_term: str, location: str, sites: list[str]):
    """Run JobSpy and return a pandas DataFrame (may be empty)."""
    return scrape_jobs(
        site_name=sites,
        search_term=search_term,
        location=location,
        hours_old=24,
        country_indeed="India",
        results_wanted=50,
    )


# ---------------------------------------------------------------------------
# LangGraph tools
# ---------------------------------------------------------------------------

@tool
def scrape_jobs_tool(search_term: str, location: str, sites: list[str]) -> str:
    """Scrape job listings and return a summary count with sample titles.

    Args:
        search_term: Job role to search for (e.g. "data analyst").
        location: City/area string (e.g. "Hyderabad").
        sites: List of job sites to scrape, e.g. ["linkedin", "indeed", "naukri"].
    """
    try:
        df = _scrape(search_term, location, sites)
        if df is None or df.empty:
            return f"No jobs found for '{search_term}' in '{location}'."

        count = len(df)
        sample_titles = df["title"].dropna().head(5).tolist()
        samples = "\n".join(f"  - {t}" for t in sample_titles)
        return (
            f"Found {count} job(s) for '{search_term}' in '{location}'.\n"
            f"Sample titles:\n{samples}"
        )
    except Exception as exc:
        return f"Error scraping jobs: {exc}"


@tool
def save_jobs_tool(search_term: str, location: str, sites: list[str]) -> str:
    """Scrape jobs, filter by experience, and upsert them into Supabase.

    Args:
        search_term: Job role to search for (e.g. "data analyst").
        location: City/area string (e.g. "Hyderabad").
        sites: List of job sites to scrape, e.g. ["linkedin", "indeed", "naukri"].
    """
    try:
        df = _scrape(search_term, location, sites)
        if df is None or df.empty:
            return f"No jobs found for '{search_term}' in '{location}'. Nothing saved."

        supabase = _get_supabase()
        saved = skipped_senior = skipped_error = 0

        for _, row in df.iterrows():
            try:
                title = str(row.get("title") or "")
                company = str(row.get("company") or "")
                loc = str(row.get("location") or location)
                description = str(row.get("description") or "")
                job_url = str(row.get("job_url") or "")
                salary = str(row.get("min_amount") or row.get("salary_source") or "")
                site = str(row.get("site") or "")

                # Determine posted_date
                date_posted = row.get("date_posted")
                if date_posted is not None:
                    if hasattr(date_posted, "date"):
                        posted_date = date_posted.date().isoformat()
                    else:
                        posted_date = str(date_posted)
                else:
                    posted_date = date.today().isoformat()

                exp_min, exp_max = _parse_experience(description)

                # Skip jobs that are too senior
                if exp_max is not None and exp_max > 5:
                    skipped_senior += 1
                    continue

                record = {
                    "job_id": _job_id(title, company, loc),
                    "title": title,
                    "company": company,
                    "location": loc,
                    "city": "Hyderabad",
                    "experience_min": exp_min,
                    "experience_max": exp_max,
                    "is_gap_friendly": _is_gap_friendly(title, description),
                    "job_type": _classify_job_type(title, description),
                    "skills": _extract_skills(description),
                    "salary": salary or None,
                    "source": site,
                    "source_url": job_url,
                    "description": description or None,
                    "posted_date": posted_date,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }

                supabase.table("jobs").upsert(
                    record, on_conflict="job_id"
                ).execute()
                saved += 1

            except Exception as row_exc:
                skipped_error += 1
                continue

        return (
            f"Saved {saved} job(s) for '{search_term}'. "
            f"Skipped {skipped_senior} too-senior, {skipped_error} errors."
        )
    except Exception as exc:
        return f"Error in save_jobs_tool: {exc}"


@tool
def check_gap_friendly_count() -> str:
    """Query Supabase for the number of gap-friendly jobs posted today."""
    try:
        supabase = _get_supabase()
        today = date.today().isoformat()
        result = (
            supabase.table("jobs")
            .select("id", count="exact")
            .eq("is_gap_friendly", True)
            .eq("posted_date", today)
            .execute()
        )
        count = result.count if result.count is not None else len(result.data)
        return f"Gap-friendly jobs posted today ({today}): {count}"
    except Exception as exc:
        return f"Error querying gap-friendly count: {exc}"


@tool
def check_today_stats() -> str:
    """Return today's total jobs, breakdown by job_type, and gap-friendly count."""
    try:
        supabase = _get_supabase()
        today = date.today().isoformat()

        total_result = (
            supabase.table("jobs")
            .select("id", count="exact")
            .eq("posted_date", today)
            .execute()
        )
        total = total_result.count if total_result.count is not None else len(total_result.data)

        breakdown: dict[str, int] = {}
        for jtype in ("fulltime", "remote", "hybrid", "walkin"):
            r = (
                supabase.table("jobs")
                .select("id", count="exact")
                .eq("posted_date", today)
                .eq("job_type", jtype)
                .execute()
            )
            breakdown[jtype] = r.count if r.count is not None else len(r.data)

        gap_result = (
            supabase.table("jobs")
            .select("id", count="exact")
            .eq("posted_date", today)
            .eq("is_gap_friendly", True)
            .execute()
        )
        gap_count = gap_result.count if gap_result.count is not None else len(gap_result.data)

        breakdown_str = ", ".join(f"{k}: {v}" for k, v in breakdown.items())
        return (
            f"Today ({today}) stats — "
            f"Total: {total} | "
            f"By type: {breakdown_str} | "
            f"Gap-friendly: {gap_count}"
        )
    except Exception as exc:
        return f"Error querying today's stats: {exc}"
