import os

import psycopg2
from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()

app = Flask(__name__)

APP_VERSION = "1.0"
APP_NAME = "flask-lab"
DB_UNAVAILABLE_RESPONSE = ({"message": "Database not available"}, 503)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", 5432),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


def get_connection():
    print("Connecting to database with config:", DB_CONFIG)
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


@app.route("/version", methods=["GET"])
def version():
    return jsonify({"version": APP_VERSION, "app": APP_NAME}), 200


@app.route("/items", methods=["POST"])
def create_item():
    data = request.get_json()
    name = data.get("name")
    description = data.get("description", "")

    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO items (name, description) VALUES (%s, %s) RETURNING id;",
            (name, description)
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
    except psycopg2.OperationalError:
        return jsonify(DB_UNAVAILABLE_RESPONSE[0]), DB_UNAVAILABLE_RESPONSE[1]

    return jsonify({"id": new_id, "name": name, "description": description}), 201


@app.route("/items/name/<string:name>", methods=["GET"])
def get_item_by_name(name):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, description FROM items WHERE name = %s;", (name,))
        row = cur.fetchone()
        cur.close()
        conn.close()
    except psycopg2.OperationalError:
        return jsonify(DB_UNAVAILABLE_RESPONSE[0]), DB_UNAVAILABLE_RESPONSE[1]

    if row is None:
        return jsonify({"error": "item not found"}), 404

    return jsonify({"id": row[0], "name": row[1], "description": row[2]}), 200


@app.route("/items", methods=["GET"])
def get_items():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, description FROM items;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except psycopg2.OperationalError:
        return jsonify(DB_UNAVAILABLE_RESPONSE[0]), DB_UNAVAILABLE_RESPONSE[1]

    items = [{"id": r[0], "name": r[1], "description": r[2]} for r in rows]
    return jsonify(items), 200


try:
    init_db()
except psycopg2.OperationalError as e:
    print(f"Database not available at startup, skipping init_db: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("APP_PORT", 5000)))  # nosec B104
