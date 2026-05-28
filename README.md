# Fresher Jobs — Data Analyst Hyderabad

Scrapes LinkedIn, Indeed, and Naukri every 4 hours for data analyst jobs in Hyderabad suited to candidates with ~3 years of experience, including those with a career gap.
All jobs are stored in Supabase and served via a FastAPI backend. Total infrastructure cost: ₹0/month.

---

## Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/your-username/fresher-jobs.git
   cd fresher-jobs
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS / Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in the four keys (all free, no credit card):

   | Variable | Where to get it |
   |---|---|
   | `GOOGLE_API_KEY` | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
   | `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) |
   | `SUPABASE_URL` | Supabase → your project → Settings → API |
   | `SUPABASE_KEY` | Supabase → your project → Settings → API |

5. **Create the Supabase `jobs` table**

   Go to [supabase.com](https://supabase.com) → your project → **SQL Editor** and run:

   ```sql
   create table if not exists jobs (
     id              bigserial primary key,
     job_id          text unique not null,
     title           text,
     company         text,
     location        text,
     city            text default 'Hyderabad',
     experience_min  integer,
     experience_max  integer,
     is_gap_friendly boolean default false,
     job_type        text check (job_type in ('fulltime', 'remote', 'hybrid', 'walkin')),
     skills          text[],
     salary          text,
     source          text,
     source_url      text,
     description     text,
     posted_date     date,
     scraped_at      timestamptz default now()
   );
   create index if not exists idx_jobs_posted_date   on jobs (posted_date);
   create index if not exists idx_jobs_gap_friendly  on jobs (is_gap_friendly, posted_date);
   create index if not exists idx_jobs_job_type      on jobs (job_type, posted_date);
   ```

---

## Run locally

**Scrape jobs once (agent)**
```bash
python -m agent.agent
```

**Start the API server**
```bash
uvicorn api.main:app --reload
```

API docs available at [http://localhost:8000/docs](http://localhost:8000/docs)

**Key endpoints**

| Endpoint | Description |
|---|---|
| `GET /jobs` | Paginated list with filters (`job_type`, `gap_friendly`, `search`) |
| `GET /jobs/{job_id}` | Full detail for one job |
| `GET /stats` | Today's totals, type breakdown, top companies, top skills |
| `GET /walkins` | Walk-in interviews posted today |
| `GET /gap-friendly` | Gap-friendly jobs posted today |

---

## Deploy

### Backend → Render.com (free)

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo.
3. Set the following in Render's dashboard:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - **Environment variables:** add `SUPABASE_URL` and `SUPABASE_KEY` (Render doesn't need the LLM keys).
4. Deploy. Render gives you a public URL like `https://fresher-jobs.onrender.com`.

### Frontend → Vercel (free)

1. Create a Next.js app:
   ```bash
   npx create-next-app@latest frontend
   ```
2. Set `NEXT_PUBLIC_API_URL=https://fresher-jobs.onrender.com` in Vercel's environment variables.
3. Push and connect to [vercel.com](https://vercel.com) — it auto-deploys on every push.

### Scheduler → GitHub Actions (free)

The workflow in `.github/workflows/scrape.yml` runs every 4 hours automatically.

Add these four secrets in GitHub → Settings → Secrets and variables → Actions:
- `GOOGLE_API_KEY`
- `GROQ_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

You can also trigger a scrape manually from the **Actions** tab → **Scrape Jobs** → **Run workflow**.
