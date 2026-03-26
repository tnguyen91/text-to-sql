import os
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text, inspect
from anthropic import Anthropic
from dotenv import load_dotenv

# Load secrets from .env file
load_dotenv()

# Set up Flask
app = Flask(__name__)

# Connect to PostgreSQL database
engine = create_engine(os.getenv("DB_URL"))

# Set up the Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MAX_RETRIES = 3


def get_schema_description():
    inspector = inspect(engine)
    schema_parts = []

    for table_name in inspector.get_table_names():
        if table_name == "query_history":
            continue

        columns = inspector.get_columns(table_name)
        column_descriptions = []
        for col in columns:
            column_descriptions.append(f"  {col['name']} ({col['type']})")

        foreign_keys = inspector.get_foreign_keys(table_name)
        fk_descriptions = []
        for fk in foreign_keys:
            fk_descriptions.append(
                f"  FOREIGN KEY ({', '.join(fk['constrained_columns'])}) "
                f"REFERENCES {fk['referred_table']}({', '.join(fk['referred_columns'])})"
            )

        table_desc = f"Table: {table_name}\nColumns:\n" + "\n".join(column_descriptions)
        if fk_descriptions:
            table_desc += "\nForeign Keys:\n" + "\n".join(fk_descriptions)

        schema_parts.append(table_desc)

    return "\n\n".join(schema_parts)

def generate_sql(user_question, schema, failed_sql=None, error_message=None):
    system_prompt = (
        "You are a SQL expert. Given the following PostgreSQL database schema, "
        "write a SQL query to answer the user's question.\n\n"
        "RULES:\n"
        "- Return ONLY the SQL query, no explanation, no markdown, no code fences\n"
        "- Use only SELECT statements (never INSERT, UPDATE, DELETE, DROP, etc.)\n"
        "- Use proper JOIN syntax when combining tables\n"
        "- Always alias columns for readability\n"
        f"\nDATABASE SCHEMA:\n{schema}"
    )
 
    # Build the message
    if failed_sql and error_message:
        user_content = (
            f"Original question: {user_question}\n\n"
            f"I tried this SQL but it failed:\n{failed_sql}\n\n"
            f"The database returned this error:\n{error_message}\n\n"
            "Please fix the SQL query. Return ONLY the corrected SQL, nothing else."
        )
    else:
        user_content = user_question
 
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": user_content,
            }
        ],
    )
 
    return response.content[0].text.strip()

def validate_sql(sql = None):
    if not sql:
        return False, "No SQL provided."

    sql_upper = sql.upper().strip()

    # Must start with SELECT or WITH (for CTEs)
    if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
        return False, "Only SELECT queries are allowed."

    # Block dangerous keywords
    dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "EXEC", "EXECUTE"]
    for keyword in dangerous:
        if f" {keyword} " in f" {sql_upper} ":
            return False, f"Query contains forbidden keyword: {keyword}"

    return True, "OK"

def execute_sql(sql):
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchall()]
 
        # Convert any non-serializable types (like Decimal) to float
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                if hasattr(val, "as_integer_ratio"):  # It's a Decimal
                    rows[i][j] = float(val)
                elif hasattr(val, "isoformat"):  # It's a date
                    rows[i][j] = val.isoformat()
 
    return columns, rows

def save_query(question, sql, success, attempts, error_message=None, row_count=None):
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO query_history (question, generated_sql, success, attempts, error_message, row_count) "
                    "VALUES (:question, :sql, :success, :attempts, :error, :row_count)"
                ),
                {
                    "question": question,
                    "sql": sql,
                    "success": success,
                    "attempts": attempts,
                    "error": error_message,
                    "row_count": row_count,
                },
            )
            conn.commit()
    except Exception:
        pass  # Don't let history-saving errors break the main app

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/query", methods=["POST"])
def handle_query():
    data = request.get_json(silent=True) or {}
    user_question = (data.get("question") or "").strip()
 
    if not user_question:
        return jsonify({"error": "Please enter a question."}), 400
 
    # Get the schema (once - reused across retries)
    schema = get_schema_description()
 
    # Track all attempts for transparency
    attempts = []
    last_sql = None
    last_error = None
 
    for attempt in range(1, MAX_RETRIES + 1):
        sql = None
        try:
            # Generate SQL (with error context if retrying)
            if attempt == 1:
                sql = generate_sql(user_question, schema)
            else:
                sql = generate_sql(user_question, schema, last_sql, last_error)
 
            # Validate the SQL
            is_safe, message = validate_sql(sql)
            if not is_safe:
                last_sql = sql
                last_error = f"Validation failed: {message}"
                attempts.append({
                    "attempt": attempt,
                    "sql": sql,
                    "error": last_error,
                })
                continue  # Try again
 
            # Execute the query
            columns, rows = execute_sql(sql)
 
            # Success - Return results with attempt info
            result = {
                "sql": sql,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "attempts": attempt,
            }
 
            # If it took retries, include the history so the user can see
            if attempt > 1:
                result["retry_history"] = attempts
 
            save_query(user_question, sql, True, attempt, row_count=len(rows))

            return jsonify(result)
 
        except Exception as e:
            last_sql = sql
            last_error = str(e)
            attempts.append({
                "attempt": attempt,
                "sql": sql or "",
                "error": last_error,
            })
            # Continue to next retry (unless we've exhausted attempts)
 
    save_query(user_question, last_sql, False, MAX_RETRIES, error_message=last_error)

    # All retries failed
    return jsonify({
        "error": f"Failed after {MAX_RETRIES} attempts. Last error: {last_error}",
        "sql": last_sql,
        "retry_history": attempts,
    })

@app.route("/history")
def get_history():
    """Return the 20 most recent queries."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT id, question, generated_sql, success, attempts, row_count, created_at "
                "FROM query_history ORDER BY created_at DESC LIMIT 20"
            )
        )
        history = []
        for row in result.fetchall():
            history.append({
                "id": row[0],
                "question": row[1],
                "sql": row[2],
                "success": row[3],
                "attempts": row[4],
                "row_count": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
            })
    return jsonify(history)

if __name__ == "__main__":
    app.run(debug=True)