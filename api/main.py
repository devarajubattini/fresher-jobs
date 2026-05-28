import os
from collections import Counter
from datetime import date
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from supabase import create_client, Client

load_dotenv()

# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

_supabase: Client | None = None


def _db() -> Client:
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL", "https://okvujfdvowndvnsezgfj.supabase.co")
        key = os.getenv("SUPABASE_KEY", "sb_publishable_d5D8KWOhqq4hnbzgqnHJFg_ZMt6XdAi")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set.")
        _supabase = create_client(url, key)
    return _supabase


# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Fresher Jobs API",
    description="Data analyst jobs in Hyderabad — gap-friendly & freshers",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

CACHE_15MIN = "public, max-age=900"

SKILLS_LIST = [
    "SQL", "Python", "Excel", "Power BI", "Tableau", "Looker",
    "Google Analytics", "Data Studio", "MS Excel", "pivot tables",
    "VLOOKUP", "ETL", "data cleaning", "data visualization",
    "dashboards", "reporting", "MySQL", "PostgreSQL",
]

JOB_COLUMNS = (
    "job_id,title,company,location,city,experience_min,experience_max,"
    "is_gap_friendly,job_type,skills,salary,source,source_url,posted_date,scraped_at"
)

JOB_DETAIL_COLUMNS = JOB_COLUMNS + ",description"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_common_filters(query, *, job_type, gap_friendly, posted_today):
    if job_type and job_type != "all":
        query = query.eq("job_type", job_type)
    if gap_friendly:
        query = query.eq("is_gap_friendly", True)
    if posted_today:
        query = query.eq("posted_date", date.today().isoformat())
    return query


def _cached(data) -> JSONResponse:
    return JSONResponse(content=data, headers={"Cache-Control": CACHE_15MIN})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/jobs")
def list_jobs(
    job_type: Literal["remote", "hybrid", "walkin", "fulltime", "all"] = Query(
        default="all", description="Filter by job type"
    ),
    gap_friendly: bool = Query(default=False, description="Only gap-friendly jobs"),
    search: str | None = Query(default=None, description="Text search on title / company"),
    posted_today: bool = Query(default=True, description="Only jobs posted today"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List jobs with optional filters. Returns paginated results."""
    try:
        db = _db()
        query = db.table("jobs").select(JOB_COLUMNS)
        query = _apply_common_filters(
            query, job_type=job_type, gap_friendly=gap_friendly, posted_today=posted_today
        )

        if search:
            # Supabase full-text / ilike — search title and company
            query = query.or_(
                f"title.ilike.%{search}%,company.ilike.%{search}%"
            )

        query = (
            query
            .order("scraped_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        result = query.execute()
        return _cached({"jobs": result.data, "count": len(result.data), "offset": offset})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Full detail for a single job by its job_id (MD5 hash)."""
    try:
        result = (
            _db()
            .table("jobs")
            .select(JOB_DETAIL_COLUMNS)
            .eq("job_id", job_id)
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found.")
        return _cached(result.data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/stats")
def stats():
    """Today's totals, type breakdown, gap-friendly count, top companies, top skills."""
    try:
        db = _db()
        today = date.today().isoformat()

        # Fetch only the lightweight columns needed for stats
        result = (
            db.table("jobs")
            .select("company,job_type,is_gap_friendly,skills")
            .eq("posted_date", today)
            .execute()
        )
        rows = result.data or []

        total = len(rows)
        type_counts: dict[str, int] = {"fulltime": 0, "remote": 0, "hybrid": 0, "walkin": 0}
        gap_count = 0
        company_counter: Counter = Counter()
        skill_counter: Counter = Counter()

        for row in rows:
            jtype = row.get("job_type") or "fulltime"
            if jtype in type_counts:
                type_counts[jtype] += 1

            if row.get("is_gap_friendly"):
                gap_count += 1

            company = row.get("company")
            if company:
                company_counter[company] += 1

            for skill in row.get("skills") or []:
                skill_counter[skill] += 1

        return _cached({
            "date": today,
            "total_jobs": total,
            "by_job_type": type_counts,
            "gap_friendly": gap_count,
            "top_companies": [
                {"company": c, "count": n}
                for c, n in company_counter.most_common(10)
            ],
            "top_skills": [
                {"skill": s, "count": n}
                for s, n in skill_counter.most_common(10)
            ],
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/walkins")
def walkins(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Walk-in interviews posted today."""
    try:
        result = (
            _db()
            .table("jobs")
            .select(JOB_COLUMNS)
            .eq("job_type", "walkin")
            .eq("posted_date", date.today().isoformat())
            .order("scraped_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return _cached({"jobs": result.data, "count": len(result.data), "offset": offset})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/gap-friendly")
def gap_friendly_jobs(
    job_type: Literal["remote", "hybrid", "walkin", "fulltime", "all"] = Query(
        default="all", description="Further filter by job type"
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Gap-friendly jobs posted today."""
    try:
        db = _db()
        query = (
            db.table("jobs")
            .select(JOB_COLUMNS)
            .eq("is_gap_friendly", True)
            .eq("posted_date", date.today().isoformat())
        )
        if job_type != "all":
            query = query.eq("job_type", job_type)

        result = (
            query
            .order("scraped_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return _cached({"jobs": result.data, "count": len(result.data), "offset": offset})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Health check (useful for Render.com keep-alive pings)
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "date": date.today().isoformat()}
