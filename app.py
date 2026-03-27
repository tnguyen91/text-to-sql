import os
import re
import pandas as pd
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, text, inspect
from anthropic import Anthropic
from dotenv import load_dotenv

# Load secrets from .env file
load_dotenv()

# Set up Flask
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB max upload size

# Connect to PostgreSQL database
engine = create_engine(os.getenv("DB_URL"))

# Set up the Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MAX_RETRIES = 3

# Sample data tables
PROTECTED_TABLES = {"categories", "customers", "products", "orders", "order_items", "reviews", "query_history"}


def get_schema_description(selected_tables=None):
    inspector = inspect(engine)
    schema_parts = []

    for table_name in inspector.get_table_names():
        if table_name == "query_history":
            continue

        # If the user selected specific tables, only include those
        if selected_tables and table_name not in selected_tables:
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
        "- ONLY use tables and columns that exist in the schema below\n"
        f"\nDATABASE SCHEMA:\n{schema}"
    )

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


def validate_sql(sql=None):
    if not sql:
        return False, "No SQL provided."

    sql_upper = sql.upper().strip()

    if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
        return False, "Only SELECT queries are allowed."

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

        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                if hasattr(val, "as_integer_ratio"):
                    rows[i][j] = float(val)
                elif hasattr(val, "isoformat"):
                    rows[i][j] = val.isoformat()

    return columns, rows


def save_query(question, sql, success, attempts, error_message=None, row_count=None):
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO query_history "
                    "(question, generated_sql, success, attempts, error_message, row_count) "
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
        pass


def sanitize_table_name(name):
    name = os.path.splitext(name)[0]
    name = re.sub(r"[^a-zA-Z0-9]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    name = name.lower()
    if name and name[0].isdigit():
        name = "t_" + name
    name = name[:63]
    return name or "uploaded_data"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/history")
def get_history():
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


@app.route("/tables")
def list_tables():
    inspector = inspect(engine)
    tables = []
    for table_name in inspector.get_table_names():
        if table_name == "query_history":
            continue
        with engine.connect() as conn:
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        tables.append({
            "name": table_name,
            "row_count": count,
            "column_count": len(columns),
            "columns": columns,
            "is_sample": table_name in PROTECTED_TABLES,
        })
    return jsonify(tables)


@app.route("/upload", methods=["POST"])
def upload_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({"error": "No file selected."}), 400

    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only CSV files are supported."}), 400

    table_name = sanitize_table_name(file.filename)

    if table_name in PROTECTED_TABLES:
        table_name = "uploaded_" + table_name

    try:
        df = pd.read_csv(file)

        if df.empty:
            return jsonify({"error": "The CSV file is empty."}), 400

        if len(df.columns) < 1:
            return jsonify({"error": "The CSV file has no columns."}), 400

        df.columns = [
            re.sub(r"[^a-zA-Z0-9]", "_", col).strip("_").lower()
            for col in df.columns
        ]

        with engine.connect() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
            conn.commit()

        df.to_sql(table_name, engine, index=False, if_exists="replace")

        return jsonify({
            "message": f"Table '{table_name}' created successfully.",
            "table_name": table_name,
            "row_count": len(df),
            "columns": list(df.columns),
        })

    except pd.errors.EmptyDataError:
        return jsonify({"error": "The CSV file is empty or malformed."}), 400
    except pd.errors.ParserError as e:
        return jsonify({"error": f"Could not parse CSV: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


@app.route("/tables/<table_name>", methods=["DELETE"])
def delete_table(table_name):
    if table_name in PROTECTED_TABLES:
        return jsonify({"error": "Cannot delete sample data tables."}), 403

    try:
        inspector = inspect(engine)
        if table_name not in inspector.get_table_names():
            return jsonify({"error": f"Table '{table_name}' not found."}), 404

        with engine.connect() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
            conn.commit()

        return jsonify({"message": f"Table '{table_name}' deleted."})
    except Exception as e:
        return jsonify({"error": f"Failed to delete table: {str(e)}"}), 500


@app.route("/query", methods=["POST"])
def handle_query():
    data = request.get_json(silent=True) or {}
    user_question = (data.get("question") or "").strip()
    selected_tables = data.get("tables")  # None means "use all tables"

    if not user_question:
        return jsonify({"error": "Please enter a question."}), 400

    schema = get_schema_description(selected_tables)

    if not schema.strip():
        return jsonify({"error": "No tables selected. Please select at least one table."}), 400

    attempts = []
    last_sql = None
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        sql = None
        try:
            if attempt == 1:
                sql = generate_sql(user_question, schema)
            else:
                sql = generate_sql(user_question, schema, last_sql, last_error)

            is_safe, message = validate_sql(sql)
            if not is_safe:
                last_sql = sql
                last_error = f"Validation failed: {message}"
                attempts.append({
                    "attempt": attempt,
                    "sql": sql,
                    "error": last_error,
                })
                continue

            columns, rows = execute_sql(sql)

            result = {
                "sql": sql,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "attempts": attempt,
            }

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

    save_query(user_question, last_sql, False, MAX_RETRIES, error_message=last_error)

    return jsonify({
        "error": f"Failed after {MAX_RETRIES} attempts. Last error: {last_error}",
        "sql": last_sql,
        "retry_history": attempts,
    })


if __name__ == "__main__":
    app.run(debug=True)