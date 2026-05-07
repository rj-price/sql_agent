# SQL Agent - Full Stack Web App

A production-ready full stack web application that translates natural language questions into SQL queries, executes them against a MySQL database, and provides human-readable answers with a self-correction mechanism.

## Architecture

- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite
- **Database**: MySQL
- **LLM**: Google Gemini 2.5 Flash

## Project Structure

```
sql_agent/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py
│   │   ├── core/
│   │   │   └── config.py
│   │   ├── db/
│   │   │   └── session.py
│   │   ├── models/
│   │   ├── services/
│   │   │   └── sql_agent.py
│   │   └── __init__.py
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .env
└── .example.env
```

## Setup

### 1. Environment Variables

Create a `.env` file in the root directory:

```ini
GOOGLE_API_KEY=your_gemini_api_key
SQL_HOST=localhost
SQL_USER=your_mysql_user
SQL_PASSWORD=your_mysql_password
SQL_DATABASE=your_mysql_database_name
SQL_PORT=3306
```

### 2. Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`.

## API Endpoints

- `POST /api/ask` - Submit a natural language question
- `GET /api/health` - Health check

## Features

- Natural language to SQL conversion using Gemini 2.5 Flash
- Dynamic schema awareness
- SQL query review and self-correction on failure
- Natural language response generation
- Responsive React frontend with Markdown support
