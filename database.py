import os

import psycopg2
import psycopg2.extras


def get_db():
    """Open a new database connection with dict-style row access."""

    conn = psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

    return conn


def init_db():
    """Create all tables if they don't already exist. Safe to call on every boot."""

    conn = get_db()

    try:
        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS complaints (
                    id SERIAL PRIMARY KEY,
                    tracking_code TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT,
                    subject TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS complaint_messages (
                    id SERIAL PRIMARY KEY,
                    complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                    sender_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS message_images (
                    id SERIAL PRIMARY KEY,
                    message_id INTEGER NOT NULL REFERENCES complaint_messages(id) ON DELETE CASCADE,
                    image_key TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS updates (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS update_images (
                    id SERIAL PRIMARY KEY,
                    update_id INTEGER NOT NULL REFERENCES updates(id) ON DELETE CASCADE,
                    image_key TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_complaints_tracking ON complaints(tracking_code)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_complaint ON complaint_messages(complaint_id)")

        conn.commit()

    finally:
        conn.close()
