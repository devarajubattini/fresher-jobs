# Data Analyst Jobs — Hyderabad (3 Years Exp + Career Gap Friendly)

## What this is
A job aggregation agent for data analyst professionals in Hyderabad
with ~3 years experience including candidates with a 1-2 year career gap.
Scrapes LinkedIn, Naukri, Indeed every 4 hours.
Stores in Supabase. Served via FastAPI. Frontend in Next.js.

## Tech Stack
- Agent: LangGraph + Google Gemini 2.5 Flash (free tier)
- Fallback LLM: Groq (Llama 3.3 70B, free tier)
- Scraping: JobSpy (python-jobspy)
- Database: Supabase (free tier, Postgres)
- Backend API: FastAPI on Render.com (free tier)
- Frontend: Next.js on Vercel (free tier)
- Scheduler: GitHub Actions cron (free tier)
- Total infra cost: ₹0/month

## Target location
Hyderabad (include Secunderabad, HITEC City, Gachibowli,
Madhapur, Kondapur, Financial District)

## Target candidate profile
- Experience: 2.5 to 4 years (to catch ~3 yrs exp jobs)
- Career gap: 1-2 years accepted / returnship / gap-friendly roles
- Job types: Full-time, Remote, Hybrid, Walk-in interviews

## Target roles (search terms)
Primary:
  "data analyst", "business analyst", "analytics analyst",
  "MIS analyst", "reporting analyst", "BI analyst"
Secondary:
  "data analyst 3 years", "data analyst Hyderabad",
  "SQL analyst", "Power BI analyst", "Tableau analyst",
  "Excel analyst", "Python data analyst"
Gap-friendly specific:
  "career gap welcome", "returnship", "return to work",
  "gap candidates welcome", "career break accepted"

## Gap-friendly detection keywords
Title or description contains any of:
  "gap", "career break", "returnship", "return to work",
  "career gap", "break in career", "re-entry", "relaunch",
  "gap candidates", "gap year", "career pause"

## Job type classification
- remote: "remote", "work from home", "WFH", "fully remote"
- hybrid: "hybrid", "2 days office", "3 days office", "flexible"
- walkin: "walk-in", "walkin", "walk in interview", "direct interview"
- fulltime: default if none of the above match

## Skills to look for (for better ranking/filtering)
SQL, Python, Excel, Power BI, Tableau, Looker, Google Analytics,
Data Studio, MS Excel, pivot tables, VLOOKUP, ETL, data cleaning,
data visualization, dashboards, reporting, MySQL, PostgreSQL

## Supabase jobs table schema
id             bigserial primary key
job_id         text unique  -- MD5 of title+company+location
title          text
company        text
location       text
city           text default 'Hyderabad'
experience_min integer      -- parsed from description
experience_max integer
is_gap_friendly boolean default false
job_type       text         -- fulltime/remote/hybrid/walkin
skills         text[]       -- array of matched skills
salary         text
source         text         -- linkedin/naukri/indeed
source_url     text
description    text
posted_date    date
scraped_at     timestamptz default now()

## Rules
- Deduplicate using MD5 hash of title+company+location
- Only fetch jobs posted in last 24 hours (hours_old=24)
- Parse experience range from description (look for "2-4 years", "3 years" etc.)
- Filter: keep only jobs where experience_max <= 5 (exclude senior/lead/manager)
- Set is_gap_friendly=true if gap keywords found in title or description
- Extract matched skills array from description
- Agent retries with Groq if Gemini fails

## Environment variables
GOOGLE_API_KEY=     # ai.google.dev (free, no card)
GROQ_API_KEY=       # console.groq.com (free, no card)
SUPABASE_URL=       # supabase.com (free)
SUPABASE_KEY=       # supabase.com (free)