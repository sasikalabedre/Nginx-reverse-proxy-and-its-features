import os
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)


def get_conn():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS notes (id SERIAL PRIMARY KEY, text TEXT NOT NULL)")
    conn.commit()
    cur.close()
    conn.close()


@app.route("/notes", methods=["GET"])
def list_notes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM notes ORDER BY id")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"id": r[0], "text": r[1]} for r in rows])


@app.route("/notes", methods=["POST"])
def add_note():
    text = request.get_json()["text"]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO notes (text) VALUES (%s)", (text,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "saved"}), 201


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
