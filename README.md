# Text-to-SQL Explorer

A web app that lets you query a PostgreSQL database using plain English. It uses Claude to generate SQL from your question, validates it, runs it, and displays the results.

Built with Flask, PostgreSQL, SQLAlchemy, and the Anthropic API.

## How it works

1. User types a question in plain English
2. The app reads the database schema using SQLAlchemy's `inspect()`
3. The schema + question are sent to Claude, which generates a SQL query
4. The SQL is validated (read-only, no destructive keywords)
5. The query runs against PostgreSQL and results are returned
6. If the query fails, the error is fed back to Claude for self-correction (up to 3 retries)

## Database

The sample database models a small e-commerce store with 6 tables:

- `categories` - product categories
- `customers` - customer profiles with location data
- `products` - product catalog linked to categories
- `orders` - order records with status tracking
- `order_items` - line items within each order
- `reviews` - customer product reviews (1-5 rating)

See `schema.sql` for the full schema and seed data.

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
DB_URL=postgresql://postgres:yourpassword@localhost:5432/textosql
```

### Run

```bash
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

## Project structure

```
text-to-sql/
├── app.py              # Flask app, routes, LLM integration, SQL validation
├── templates/
│   └── index.html      # Frontend UI
├── schema.sql          # Database schema and seed data
├── requirements.txt    # Python dependencies
├── .env                # API keys and DB credentials (not committed)
└── .gitignore
```

## Security

- Only SELECT/WITH queries are allowed. Destructive keywords (DROP, DELETE, ALTER, etc.) are blocked before execution.
- API keys and DB credentials are stored in `.env` and excluded from version control.

## Future improvements

- Query history and caching
- Chart visualization for numeric results
- Docker Compose setup
- Test suite for SQL validation and schema introspection
- Rate limiting on the API endpoint

## License

MIT
