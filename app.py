"""TaskBoard Demo - Flask + SQLite task management app."""

import sqlite3
from flask import Flask, g

app = Flask(__name__)
app.config['SECRET_KEY'] = 'taskboard-demo-secret-key-2026'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = False
DATABASE = "taskboard.db"


def get_db():
    """Get a raw sqlite3 connection (no ORM)."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database from schema.sql."""
    with app.app_context():
        db = get_db()
        with app.open_resource("schema.sql", mode="r") as f:
            db.executescript(f.read())
        db.commit()


@app.route("/")
def index():
    return "<h1>TaskBoard</h1><p>Welcome to TaskBoard.</p>"


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
