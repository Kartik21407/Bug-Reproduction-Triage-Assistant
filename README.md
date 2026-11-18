# Bug Reproduction & Triage Assistant

**IT314 Software Engineering — Group 9**  
*Dhirubhai Ambani University (formerly DA-IICT)*

---

## 📌 Project Overview

Bug reports submitted by testers and end users often arrive as messy, unstructured paragraphs that leave out crucial reproduction steps, expected vs. actual behaviour, logs, or system environment. 

The **Bug Reproduction & Triage Assistant** is an intelligent web application designed to turn raw, informal bug reports into structured, developer-ready issues. It automatically extracts key details using LLMs, verifies and sanitizes sensitive data (PII/secrets), flags missing reproduction info, suggests severity and priority through a deterministic rules engine, and detects duplicates against past issues using vector embeddings. 

Developers can edit generated sections, take duplicate decisions, and export finalized reports directly to GitHub as formatted issues.

---

## 🚀 Sprint Progress (Sprint 1 to Sprint 4)

This project is iteratively built across 5 Scrum sprints. Here is what has been developed and verified through **Sprint 4**:

- **Sprint 1: Core Foundation & Ingestion**
  - Project architecture setup (FastAPI + PostgreSQL + React/Vite in Docker).
  - User authentication with salted Argon2 password hashing and JWT sessions.
  - Raw bug report submission, listing, and persistent database storage.

- **Sprint 2: LLM Extraction, Masking & Clarification**
  - Automatic extraction of title, actual vs. expected behavior, repro steps, and environment.
  - Client-side and server-side secret/PII masking preview before sending data to LLM.
  - Dynamic completeness scoring and automated follow-up question generation for missing info.

- **Sprint 3: Triage Engine & Semantic Duplicate Detection**
  - Deterministic triage rules engine suggesting bug severity, priority, and reproducibility.
  - Vector duplicate search using local embeddings (`sentence-transformers/all-MiniLM-L6-v2` via FastEmbed).
  - CLI utility to ingest and index historical GitHub bug issues into vector storage.

- **Sprint 4: Human-in-the-Loop Refinement & GitHub Integration**
  - Section-by-section inline report editing with override persistence surviving re-analysis.
  - Duplicate candidate decisions (marking candidates as *Duplicate* or *Not a Duplicate*).
  - Secure GitHub integration: Fernet-encrypted Personal Access Token (PAT) storage and direct issue filing.
  - Interactive Analytics dashboard tracking triage acceptance rates and bug volume over time.

- **Sprint 5 (Upcoming):**
  - Final end-to-end integration testing, UI polish, and production deployment configuration.

---

## 🏗️ Architecture & Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2
- **Database & Storage:** PostgreSQL 16, pgvector
- **AI & NLP:** Google Gemini Flash API (field extraction & follow-up questions)
- **Vector Search:** FastEmbed (`all-MiniLM-L6-v2`) for local cosine similarity search
- **Security:** Argon2 hashing, Fernet symmetric encryption for stored GitHub tokens
- **Frontend:** TypeScript, React 18, Vite, Tailwind CSS, TanStack React Query, Recharts, Lucide Icons
- **Testing & Quality:** Pytest (400+ unit & integration tests), Ruff, Vitest, Pre-commit hooks
- **Infrastructure:** Docker & Docker Compose multi-container stack

---

## 💻 Quickstart & Local Setup

### Prerequisites
- [Docker Desktop](https://www.docker.com/) (or Docker Engine with Compose)
- [Node.js 20+](https://nodejs.org/) & npm
- [Python 3.12+](https://www.python.org/)
- Git

### 1. Clone & Setup Environment

```bash
git clone https://github.com/Kartik21407/Bug-Reproduction-Triage-Assistant.git
cd Bug-Reproduction-Triage-Assistant
```

Create `.env` from template:
```bash
cp .env.example .env
```

Generate secure secrets for JWT and GitHub token encryption:
```bash
# JWT Secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Fernet Key for GitHub PAT encryption
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Paste both generated keys into `.env` under `JWT_SECRET_KEY` and `TOKEN_ENCRYPTION_KEY`.

---

### 2. Run with Docker Compose

Start the full stack (PostgreSQL, Backend API, and Vite Frontend):
```bash
docker compose up --build
```

- **Frontend Client:** http://localhost:5173
- **FastAPI Docs (Swagger UI):** http://localhost:8000/docs
- **Database:** `localhost:5432`

---

### 3. Apply Database Migrations

Apply Alembic migrations to set up all tables and relationships:
```bash
docker compose exec backend alembic upgrade head
```

---

### 4. Seed the Duplicate Detection Corpus

Index real-world bug issues to enable vector search matching:
```bash
# Fetch bug issues from an open-source project
docker compose exec backend python -m app.corpus.cli fetch-github nextcloud/server --label bug --limit 300 --out /tmp/issues.json

# Import and compute FastEmbed embeddings
docker compose exec backend python -m app.corpus.cli import /tmp/issues.json
```

---

## 🧪 Running Tests & Quality Checks

### Backend (Python)
From `backend/`:
```bash
# Linting & Formatting
ruff check .
ruff format --check .

# Run pytest suite
pytest
```

### Frontend (React)
From `frontend/`:
```bash
# Linting & Formatting
npm run lint
npm run format:check

# Run Vitest suite
npm run test
```

---

## 📁 Repository Structure

```text
├── backend/
│   ├── alembic/              # Database migration scripts
│   ├── app/
│   │   ├── analysis/         # Extraction prompts, schema & verification
│   │   ├── api/              # REST routes (auth, reports, duplicates, github, analytics)
│   │   ├── corpus/           # Embeddings generator & vector search
│   │   ├── github/           # GitHub REST client & Fernet security
│   │   ├── models/           # SQLAlchemy database entities
│   │   ├── report/           # Report persistence store & Markdown export
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── triage/           # Rules engine for severity & priority
│   └── tests/                # Full pytest test suite (models, api, report)
├── frontend/
│   ├── src/
│   │   ├── components/       # UI components, section editor & charts
│   │   ├── hooks/            # Custom React Query hooks
│   │   ├── pages/            # Application views (Report, Review, GitHub, Analytics)
│   │   ├── types/            # TypeScript contracts
│   │   └── router.tsx        # Application routing
│   └── src/tests/            # Vitest unit & integration tests
├── docs/                     # Specifications, sprint plans & ADRs
├── docker-compose.yml        # Multi-container orchestration
└── requirements.txt          # Python dependencies
```

---

## 👥 Team Members (Group 9)

| Name | Student ID |
| :--- | :--- |
| **Kartik Shah** | 202401084 |
| **Katuri Anushree** | 202401086 |
| **Muneet Sadhwani** | 202401123 |
| **Kevin Rank** | 202401091 |
| **Dhruv Nagani** | 202401124 |
| **Harshil Patel** | 202401144 |
| **Dev Parmar** | 202401138 |
| **Priyanshi Kotadiya** | 202401097 |
| **Yashraj Jadeja** | 202401072 |
| **Shubham Mishra** | 202301100 |

---

## 📄 Academic Integrity

Developed for academic evaluation under the **IT314: Software Engineering** course at **Dhirubhai Ambani University**.
