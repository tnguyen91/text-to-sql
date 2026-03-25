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


def get_schema_description():
    inspector = inspect(engine)
    schema_parts = []

    for table_name in inspector.get_table_names():
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


def generate_sql(user_question, schema):
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=(
            "You are a SQL expert. Given the following PostgreSQL database schema, "
            "write a SQL query to answer the user's question.\n\n"
            "RULES:\n"
            "- Return ONLY the SQL query, no explanation, no markdown, no code fences\n"
            "- Use only SELECT statements (never INSERT, UPDATE, DELETE, DROP, etc.)\n"
            "- Use proper JOIN syntax when combining tables\n"
            "- Always alias columns for readability\n"
            f"\nDATABASE SCHEMA:\n{schema}"
        ),
        messages=[
            {
                "role": "user",
                "content": user_question,
            }
        ],
    )

    return response.content[0].text.strip()


def validate_sql(sql):
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


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/query", methods=["POST"])
def handle_query():
    data = request.get_json()
    user_question = data.get("question", "")

    if not user_question:
        return jsonify({"error": "Please enter a question."}), 400

    try:
        # Get the schema
        schema = get_schema_description()

        # Generate SQL from the question
        sql = generate_sql(user_question, schema)

        # Validate the SQL
        is_safe, message = validate_sql(sql)
        if not is_safe:
            return jsonify({"error": f"Unsafe query blocked: {message}", "sql": sql})

        # Execute the query
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

        # Return everything
        return jsonify(
            {
                "sql": sql,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
        )

    except Exception as e:
        return jsonify({"error": str(e), "sql": sql if "sql" in dir() else None})


if __name__ == "__main__":
    app.run(debug=True)