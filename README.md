# SQL Agent

A full-stack web application that translates natural language questions into SQL queries, executes them against a MySQL database, and returns human-readable answers. Includes a self-correction loop: if the initial query fails, the LLM reviews and rewrites it before trying again.

## Architecture

| Layer | Technology |
| :--- | :--- |
| Frontend | React + Vite |
| Backend | FastAPI (Python) |
| Database | MySQL 8 |
| LLM | Google Gemini 2.5 Flash |

```
┌───────────────┐       ┌─────────────────┐       ┌──────────┐
│  React        │──────▶│  FastAPI        │──────▶│  MySQL   │
│  :5174        │◀──────│  :8002          │◀──────│  :3306   │
└───────────────┘  HTTP └─────────────────┘  SQL  └──────────┘
                                │
                                │ Gemini API
                                ▼
                     Google Gemini 2.5 Flash
```

## How It Works

1. The user types a plain-English question in the browser.
2. The backend fetches the database schema (tables, columns, sample rows) and passes it to Gemini to generate a SQL query.
3. The query is executed. Only `SELECT` and `WITH` (CTE) statements are permitted — write operations are blocked at the code level.
4. If execution succeeds, the results are sent back to Gemini to produce a conversational answer.
5. If execution fails (e.g. a hallucinated table name), Gemini reviews the broken query and suggests a correction. The corrected query is then executed and the answer generated from those results.
6. The browser displays the natural-language answer, the SQL query that ran, a results table, and — if a correction was needed — the review details.

## Project Structure

```
sql_agent/
├── backend/
│   ├── app/
│   │   ├── api/routes.py        # HTTP endpoints
│   │   ├── core/config.py       # Settings (pydantic-settings)
│   │   ├── db/session.py        # DB connection + schema extraction
│   │   └── services/
│   │       └── sql_agent.py     # LLM + query orchestration
│   ├── tests/                   # pytest test suite
│   ├── main.py                  # FastAPI app factory
│   ├── requirements.txt
│   └── requirements-test.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   └── package.json
├── docker-compose.yml
├── init.sql                     # Database seed run on first start
└── .example.env
```

## Setup

### Prerequisites

- Docker and the `docker compose` plugin
- A Google Gemini API key

### 1. Environment Variables

Copy `.example.env` to `.env` and fill in your values:

```ini
GOOGLE_API_KEY=your_gemini_api_key
SQL_HOST=db
SQL_USER=your_mysql_user
SQL_PASSWORD=your_mysql_password
SQL_DATABASE=your_database_name
SQL_PORT=3306
```

> When running with Docker Compose, set `SQL_HOST=db` to use the MySQL container hostname.

### 2. Run with Docker Compose

```bash
docker compose up --build
```

This starts all three services. The MySQL container must pass its healthcheck before the backend starts. On first run, `init.sql` is executed to create and seed the database.

| Service | URL |
| :--- | :--- |
| Frontend | http://localhost:5174 |
| Backend API | http://localhost:8002 |

### 3. Manual Setup (without Docker)

**Backend:**

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

When running manually, point `SQL_HOST` at your MySQL instance and set `VITE_API_URL=http://localhost:8000/api` in your environment before starting the frontend.

## API Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/ask` | Submit a question: `{"question": "..."}` |
| `GET` | `/api/schema` | Returns the current database schema |
| `GET` | `/api/health` | Health check |

## Running Tests

```bash
cd backend
uv venv && uv pip install -r requirements.txt -r requirements-test.txt
.venv/bin/python -m pytest tests/ -v
```
