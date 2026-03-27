# Text-to-SQL Explorer

An LLM wrapper for generating SQL queries from natural language.

Built with Flask, PostgreSQL, SQLAlchemy, and the Anthropic API.

**Live demo:** https://text-to-sql-5d9f.onrender.com

## Features

- Natural language to SQL via Claude
- Auto-retry with error self-correction (up to 3 attempts)
- CSV upload to query your own data
- Auto-generated bar/line chart visualizations
- Query history with re-run support
- SQL validation (read-only, destructive keywords blocked)

## How it works

1. User types a question in plain English
2. The app reads the database schema using SQLAlchemy's `inspect()`
3. The schema + question are sent to Claude, which generates a SQL query
4. The SQL is validated and executed against PostgreSQL
5. If the query fails, the error is fed back to Claude for self-correction

## Setup

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- [Anthropic API key](https://console.anthropic.com/)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/text-to-sql.git
cd text-to-sql

python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### Database setup

```bash
psql -U postgres
CREATE DATABASE textosql;
\c textosql
\i schema.sql
\q
```

### Environment variables

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your-api-key-here
DB_URL=postgresql://postgres:yourpassword@localhost:5433/textosql
```

### Run

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

### Docker

```bash
docker compose up --build
```

## Project structure

```
text-to-sql/
├── app.py              # Flask app, routes, LLM integration
├── templates/
│   └── index.html      # Frontend UI
├── schema.sql          # Database schema and seed data
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env                # API keys and DB credentials (not committed)
```

## License

MIT
