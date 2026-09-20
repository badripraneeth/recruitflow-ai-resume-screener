# RecruitFlow: AI-Powered Recruiter Resume Screening & Shortlisting System

A production-grade, pure Django web application for automated resume parsing, AI-assisted structured information extraction, pure deterministic candidate scoring, and recruiter shortlisting workflows.

---

## Architecture & Core Design Principles

1. **Deterministic Mathematical Scoring**:
   The LLM does **NOT** calculate the final 0–100 screening score. The LLM's sole responsibility is structured fact extraction from PDF resumes. Python's scoring engine calculates the final score strictly according to the defined weighted rubric:
   - Required Skills: **40%**
   - Preferred Skills: **15%**
   - Experience: **20%**
   - Education: **10%**
   - Projects: **15%**
   - Total: **100%** (guaranteed between 0.0 and 100.0)

2. **Resilient Dual-Mode Extraction**:
   - **Primary**: Google Gemini LLM structured fact extraction (`google-generativeai`).
   - **Fallback**: Built-in deterministic rule/regex extractor that seamlessly activates if the LLM API experiences rate limits (429 Quota Exceeded), timeouts, or connectivity issues—ensuring screening never fails or defaults to empty scores.

3. **Recruiter Responsibility & Human-in-the-Loop**:
   - Newly evaluated candidates strictly start in the `Review` status.
   - AI summaries and scores **never** automatically shortlist or reject candidates.
   - Recruiters have manual decision controls (`[Shortlist]`, `[Keep in Review]`, `[Reject]`) and evaluation notes on each candidate.

4. **Strict Recruiter Isolation (Multi-Tenancy)**:
   - Recruiters can **only** view, edit, and access jobs, resumes, and candidates they own.
   - Attempting to access another recruiter's jobs or candidates returns an immediate `404 Not Found`.
   - Superusers (`admin@gmail.com`) maintain global company visibility across all jobs and candidates.

5. **Role-Based Access Control (RBAC)**:
   - **Recruiters**: Scoped exclusively to the recruiter workspace (`/dashboard/`, `/jobs/`, `/candidates/`, `/shortlisted/`, `/upload/`). Strictly blocked from logging into the Django Admin Panel.
   - **Superusers**: Have full administrative rights and exclusive access to the Django Admin Panel (`/admin/`).

---

## Page & Workspace Architecture

- **Public**:
  - `/login/` - Secure recruiter & admin authentication.
  - `/register/` - Recruiter registration (all signups default to `recruiter` role with staff/superuser privileges disabled).
  - `/logout/` - Secure session logout.

- **Recruiter Workspace**:
  - `/` or `/dashboard/` - High-level metrics (**Active Jobs**, **Total Resumes**, **In Review**, **Shortlisted**, **Rejected**) & recent jobs overview table.
  - `/jobs/` - Recruiter's own job postings with candidate counters and quick actions (`View`, `Candidates`, `Upload`).
  - `/jobs/create/` - Job creation with optional minimum score and shortlist target thresholds.
  - `/jobs/<job_id>/` - Job overview with candidate status breakdown and direct action buttons.
  - `/jobs/<job_id>/edit/` - Edit job title, description, skills, and experience criteria.
  - `/jobs/<job_id>/delete/` - Remove job posting.
  - `/jobs/<job_id>/upload/` or `/upload/` - Multi-file resume upload with automatic text extraction, AI screening, and scoring.
  - `/jobs/<job_id>/candidates/` - Candidates Hub with multi-field search (`q`), score/experience filters, sorting, Top-N filters, and bulk actions.
  - `/jobs/<job_id>/candidates/<candidate_id>/` - In-depth candidate profile with match score, 5-part rubric breakdown, AI executive summary, extracted education & projects, recruiter decision buttons, and saved notes.
  - `/shortlisted/` - Global table of all shortlisted candidates across recruiter jobs with direct review controls.

- **Superuser Only**:
  - `/admin/` - Built-in Django Admin site (strictly restricted to `request.user.is_superuser`; all non-superusers are blocked).

- **Dynamic AJAX APIs (Pure Django / JSON)**:
  - `POST/PATCH /jobs/<job_id>/candidates/<candidate_id>/status/` - Quick candidate status updates (`review`, `shortlisted`, `rejected`).
  - `POST/PATCH /jobs/<job_id>/candidates/<candidate_id>/notes/` - Inline recruiter notes saving.
  - `POST /jobs/<job_id>/candidates/bulk-shortlist/` - Bulk shortlist selected candidates.
  - `POST /jobs/<job_id>/candidates/bulk-reject/` - Bulk reject selected candidates.
  - `POST /jobs/<job_id>/candidates/bulk-shortlist-reject-unselected/` - Shortlist selected candidates and reject remainder.

---

## Installation & Local Setup

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 14+ (or automatic fallback to SQLite for quick local development)

### 2. Clone & Setup Virtual Environment
```bash
git clone <repo-url>
cd ai_recuriter_resume_screening
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the project root:
```env
SECRET_KEY=your-secure-django-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Database Configuration (PostgreSQL)
DB_NAME=ai_recruiter_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432

# AI LLM Configuration
LLM_API_KEY=your_gemini_api_key_here
LLM_MODEL=gemini-2.5-flash
```

### 5. Apply Database Migrations
```bash
python manage.py migrate
```

### 6. Create Superuser (Admin)
```bash
python manage.py createsuperuser
```

### 7. Run Automated Test Suite
```bash
python manage.py test
```

### 8. Start the Development Server
```bash
python manage.py runserver 127.0.0.1:8000
```
Open **`http://127.0.0.1:8000/`** in your browser.

---

## Technology Stack

- **Backend Framework**: Django 6.x / 5.x (Pure Classic Django — Zero DRF dependency)
- **Authentication**: Django Standard Session Authentication (`django.contrib.auth`) with custom user model (`CustomUser`) and strict RBAC
- **Database**: PostgreSQL with `psycopg2-binary` (automatic fallback to SQLite)
- **PDF Extraction**: `pypdf` (supports file paths, uploaded file streams, and memory buffers)
- **AI / LLM Integration**: Google Gemini API (`google-generativeai`) with automatic fallback to local rule-based extractor
- **Deterministic Scoring Engine**: Pure Python 5-part weighted algorithm (40% required, 15% preferred, 20% experience, 10% education, 15% projects)
- **Frontend / UI**: Modern Executive Dark/Blue responsive UI with Server-Rendered Django Templates, CSS Grid, and dynamic AJAX workflows
