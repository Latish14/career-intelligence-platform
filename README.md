# Career Intelligence Platform (CIP)

A full-stack Career Intelligence Platform that analyzes resumes, extracts skills, compares them with real-world job market requirements, identifies skill gaps, and generates personalized learning roadmaps.

---

## Overview

Career Intelligence Platform (CIP) helps students, job seekers, and professionals understand how their current skill set aligns with industry demand.

The system:

* Parses uploaded resumes
* Extracts technical and soft skills
* Analyzes current market demand using live job data
* Detects missing skills
* Calculates placement readiness scores
* Generates personalized learning roadmaps

---

## Features

### Resume Processing

* PDF resume upload
* Resume text extraction
* Candidate information extraction
* Resume cleaning and normalization

### Skill Intelligence

* Skill extraction engine
* Skill normalization
* Skill confidence scoring
* Explicit and inferred skill detection

### Market Intelligence

* Automated job scraping
* Job cleaning and deduplication
* Market skill aggregation
* Industry demand analysis

### Gap Analysis

* Resume vs market comparison
* Missing skill detection
* Priority ranking
* Coverage percentage calculation

### Roadmap Generation

* Personalized learning roadmap
* Skill prioritization
* Estimated learning duration
* Placement readiness recommendations

### Data Persistence

* PostgreSQL integration
* Resume storage
* Report storage
* Repository architecture

### Frontend Dashboard

* Resume upload interface
* Report overview
* Skill visualization
* Missing skills display
* Learning roadmap display

---

## Project Architecture

```text
Resume Upload
      │
      ▼
Resume Parser
      │
      ▼
Skill Extraction Engine
      │
      ▼
Market Intelligence Engine
      │
      ▼
Gap Analysis Engine
      │
      ▼
Roadmap Generator
      │
      ▼
Career Report
```

---

## Technology Stack

### Backend

* Python
* FastAPI
* SQLAlchemy
* PostgreSQL
* TinyDB
* Uvicorn

### Frontend

* React
* Vite
* Axios

### Data Processing

* PDFPlumber
* Regular Expressions
* Custom Skill Extraction Engine

### Storage

* PostgreSQL
* JSON-based Market Cache (TinyDB)

---

## Current Project Structure

```text
backend/
│
├── api/
├── database/
├── models/
├── repositories/
├── schemas/
├── services/
│   ├── career_report/
│   ├── gap_analysis/
│   ├── job_engine/
│   ├── roadmap/
│   ├── resume_parser/
│   └── skill_engine/
│
└── main.py

frontend/
│
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   └── App.jsx

job_engine/
│
└── jobs.json
```

---

## API Endpoints

### Resume

```http
POST /resume/upload
```

Upload a resume and generate a career report.

### Reports

```http
GET /reports/{user_id}
```

Get all reports for a user.

```http
GET /reports/report/{report_id}
```

Get a report by ID.

```http
DELETE /reports/{report_id}
```

Delete a report.

---

## Sample Report Output

```json
{
  "candidate_name": "K. Latish",
  "target_role": "Software Engineer",
  "coverage_pct": 80,
  "placement_score": 75,
  "detected_skills": [],
  "missing_skills": [],
  "roadmap": []
}
```

---

## Setup Instructions

### Backend

```bash
cd backend

pip install -r requirements.txt

uvicorn main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

Swagger Documentation:

```text
http://127.0.0.1:8000/docs
```

---

### Frontend

```bash
cd frontend

npm install

npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

---

## Current Development Status

### Completed

* Resume Upload API
* Resume Parser
* Skill Extraction Engine
* Gap Analysis Engine
* Roadmap Generator
* PostgreSQL Integration
* Report Storage
* Frontend Dashboard
* Job Scraping Pipeline
* Market Intelligence Integration

### In Progress

* Market Data Quality Improvements
* Technical Job Filtering
* Enhanced Skill Detection

### Planned

* Authentication & User Accounts
* PostgreSQL Job Storage
* Interactive Analytics Dashboard
* Advanced Market Trend Analysis
* AI-Powered Career Recommendations
* Resume Improvement Suggestions
* Interview Readiness Scoring

---

## Future Scope

The platform can be extended into a complete AI-powered career guidance system capable of:

* Personalized career planning
* Industry trend forecasting
* Resume optimization
* Interview preparation
* Job recommendation systems
* Learning path automation

---

## Author

**K. Latish**

B.Tech Computer Science & Engineering (Data Science)

Career Intelligence Platform – Academic & Placement Project
