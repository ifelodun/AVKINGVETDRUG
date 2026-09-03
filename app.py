import os
import random
import string
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db, init_db
from storage import upload_image, public_url

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

MAX_IMAGES_PER_MESSAGE = 4


# ============================================================
# STARTUP
# ============================================================

def ensure_admin_account():
    """
    Create the first admin account from environment variables if no
    admin exists yet. Lets you bootstrap access without a public
    signup page.
    """

    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")

    if not username or not password:
        return

    conn = get_db()

    try:
        with conn.cursor() as cur:

            cur.execute("SELECT COUNT(*) AS count FROM admins")

            if cur.fetchone()["count"] == 0:

                cur.execute(
                    "INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
                    (username, generate_password_hash(password)),
                )

                conn.commit()

    finally:
        conn.close()


init_db()
ensure_admin_account()


# ============================================================
# HELPERS
# ============================================================

def generate_tracking_code():
    """Generate a unique, human-typeable tracking code like CMP-7K3F9Q."""

    conn = get_db()

    try:
        with conn.cursor() as cur:

            while True:

                suffix = "".join(
                    random.choices(string.ascii_uppercase + string.digits, k=6)
                )

                code = f"CMP-{suffix}"

                cur.execute(
                    "SELECT 1 FROM complaints WHERE tracking_code = %s", (code,)
                )

                if cur.fetchone() is None:
                    return code

    finally:
        conn.close()


def admin_required(view_func):

    @wraps(view_func)
    def wrapped(*args, **kwargs):

        if not session.get("admin_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("admin_login"))

        return view_func(*args, **kwargs)

    return wrapped


def save_message_images(message_id, files, key_prefix):
    """Upload up to MAX_IMAGES_PER_MESSAGE images and attach them to a message."""

    conn = get_db()

    try:
        with conn.cursor() as cur:

            count = 0

            for file_storage in files:

                if count >= MAX_IMAGES_PER_MESSAGE:
                    break

                if not file_storage or not file_storage.filename:
                    continue

                key = upload_image(file_storage, key_prefix)

                if key:
                    cur.execute(
                        "INSERT INTO message_images (message_id, image_key) VALUES (%s, %s)",
                        (message_id, key),
                    )
                    count += 1

        conn.commit()

    finally:
        conn.close()


def get_complaint_thread(tracking_code):
    """Fetch a complaint and its full message thread (with images), or None."""

    conn = get_db()

    try:
        with conn.cursor() as cur:

            cur.execute(
                "SELECT * FROM complaints WHERE tracking_code = %s", (tracking_code,)
            )
            complaint = cur.fetchone()

            if not complaint:
                return None, []

            cur.execute(
                """
                SELECT * FROM complaint_messages
                WHERE complaint_id = %s
                ORDER BY created_at ASC
                """,
                (complaint["id"],),
            )
            messages = cur.fetchall()

            for msg in messages:
                cur.execute(
                    "SELECT image_key FROM message_images WHERE message_id = %s",
                    (msg["id"],),
                )
                msg["image_urls"] = [
                    public_url(row["image_key"]) for row in cur.fetchall()
                ]

            return complaint, messages

    finally:
        conn.close()


def get_company_settings():
    """
    Fetch the single company_settings row, creating a default one if it
    doesn't exist yet. Returns a dict with a ready-to-use logo_url.
    """

    conn = get_db()

    try:
        with conn.cursor() as cur:

            cur.execute("SELECT * FROM company_settings ORDER BY id ASC LIMIT 1")
            settings = cur.fetchone()

            if not settings:
                cur.execute(
                    "INSERT INTO company_settings (company_name) VALUES ('Customer Care') RETURNING *"
                )
                settings = cur.fetchone()
                conn.commit()

            settings = dict(settings)
            settings["logo_url"] = (
                public_url(settings["logo_key"]) if settings.get("logo_key") else None
            )

            return settings

    finally:
        conn.close()

@app.context_processor
def inject_company_settings():
    """
    Make company settings and common template variables
    available throughout the application.
    """

    return {
        "company": get_company_settings(),
        "current_year": datetime.now().year,
    }
# ============================================================
# PUBLIC: HOME
# ============================================================

@app.route("/")
def home():

    conn = get_db()

    try:
        with conn.cursor() as cur:

            cur.execute(
                "SELECT * FROM updates ORDER BY created_at DESC LIMIT 3"
            )
            updates = cur.fetchall()

            for update in updates:
                cur.execute(
                    "SELECT image_key FROM update_images WHERE update_id = %s",
                    (update["id"],),
                )
                update["image_urls"] = [
                    public_url(row["image_key"]) for row in cur.fetchall()
                ]

    finally:
        conn.close()

    return render_template("index.html", updates=updates)


# ============================================================
# PUBLIC: SUBMIT A COMPLAINT
# ============================================================

@app.route("/complaint/new", methods=["GET", "POST"])
def submit_complaint():

    if request.method == "GET":
        return render_template("submit_complaint.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    subject = request.form.get("subject", "").strip()
    message_text = request.form.get("message", "").strip()

    if not name or not email or not subject or not message_text:
        flash("Please fill in your name, email, subject, and complaint details.", "error")
        return render_template("submit_complaint.html", form=request.form)

    tracking_code = generate_tracking_code()

    conn = get_db()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO complaints (tracking_code, name, email, phone, subject, status)
                VALUES (%s, %s, %s, %s, %s, 'open')
                RETURNING id
                """,
                (tracking_code, name, email, phone, subject),
            )
            complaint_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO complaint_messages (complaint_id, sender_type, message)
                VALUES (%s, 'customer', %s)
                RETURNING id
                """,
                (complaint_id, message_text),
            )
            message_id = cur.fetchone()["id"]

        conn.commit()

    finally:
        conn.close()

    files = request.files.getlist("images")
    save_message_images(message_id, files, f"complaints/{tracking_code}")

    # Verify this browser for the thread it just created
    verified = session.get("verified_complaints", [])
    verified.append(tracking_code)
    session["verified_complaints"] = verified

    return render_template("complaint_submitted.html", tracking_code=tracking_code)


# ============================================================
# PUBLIC: TRACK / VIEW A COMPLAINT THREAD
# ============================================================

@app.route("/complaint/track", methods=["GET", "POST"])
def track_complaint():

    if request.method == "GET":
        return render_template("track_complaint.html")

    tracking_code = request.form.get("tracking_code", "").strip().upper()
    email = request.form.get("email", "").strip().lower()

    complaint, _ = get_complaint_thread(tracking_code)

    if not complaint or complaint["email"].lower() != email:
        flash("We couldn't find a complaint matching that tracking code and email.", "error")
        return render_template("track_complaint.html")

    verified = session.get("verified_complaints", [])
    verified.append(tracking_code)
    session["verified_complaints"] = verified

    return redirect(url_for("view_complaint", tracking_code=tracking_code))


@app.route("/complaint/<tracking_code>", methods=["GET", "POST"])
def view_complaint(tracking_code):

    tracking_code = tracking_code.strip().upper()

    verified = session.get("verified_complaints", [])

    if tracking_code not in verified:
        flash("Please confirm your tracking code and email to view this complaint.", "error")
        return redirect(url_for("track_complaint"))

    complaint, messages = get_complaint_thread(tracking_code)

    if not complaint:
        flash("Complaint not found.", "error")
        return redirect(url_for("track_complaint"))

    if request.method == "POST":

        message_text = request.form.get("message", "").strip()

        if not message_text:
            flash("Please write a message before sending.", "error")
            return redirect(url_for("view_complaint", tracking_code=tracking_code))

        conn = get_db()

        try:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO complaint_messages (complaint_id, sender_type, message)
                    VALUES (%s, 'customer', %s)
                    RETURNING id
                    """,
                    (complaint["id"], message_text),
                )
                message_id = cur.fetchone()["id"]

                cur.execute(
                    "UPDATE complaints SET updated_at = NOW() WHERE id = %s",
                    (complaint["id"],),
                )

            conn.commit()

        finally:
            conn.close()

        files = request.files.getlist("images")
        save_message_images(message_id, files, f"complaints/{tracking_code}")

        return redirect(url_for("view_complaint", tracking_code=tracking_code))

    return render_template(
        "complaint_thread.html",
        complaint=complaint,
        messages=messages,
        is_admin_view=False,
    )


# ============================================================
# PUBLIC: UPDATES FEED
# ============================================================

@app.route("/updates")
def updates_feed():

    conn = get_db()

    try:
        with conn.cursor() as cur:

            cur.execute("SELECT * FROM updates ORDER BY created_at DESC")
            updates = cur.fetchall()

            for update in updates:
                cur.execute(
                    "SELECT image_key FROM update_images WHERE update_id = %s",
                    (update["id"],),
                )
                update["image_urls"] = [
                    public_url(row["image_key"]) for row in cur.fetchall()
                ]

    finally:
        conn.close()

    return render_template("updates.html", updates=updates)


# ============================================================
# ADMIN: LOGIN / LOGOUT
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "GET":
        return render_template("admin_login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    conn = get_db()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM admins WHERE username = %s", (username,))
            admin = cur.fetchone()

    finally:
        conn.close()

    if not admin or not check_password_hash(admin["password_hash"], password):
        flash("Invalid username or password.", "error")
        return render_template("admin_login.html")

    session["admin_id"] = admin["id"]
    session["admin_username"] = admin["username"]

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin_login"))


# ============================================================
# ADMIN: DASHBOARD
# ============================================================

@app.route("/admin")
@admin_required
def admin_dashboard():

    status_filter = request.args.get("status", "all")

    conn = get_db()

    try:
        with conn.cursor() as cur:

            if status_filter in ("open", "in_progress", "resolved"):
                cur.execute(
                    "SELECT * FROM complaints WHERE status = %s ORDER BY updated_at DESC",
                    (status_filter,),
                )
            else:
                cur.execute("SELECT * FROM complaints ORDER BY updated_at DESC")

            complaints = cur.fetchall()

            cur.execute(
                "SELECT status, COUNT(*) AS count FROM complaints GROUP BY status"
            )
            counts = {row["status"]: row["count"] for row in cur.fetchall()}

    finally:
        conn.close()

    return render_template(
        "admin_dashboard.html",
        complaints=complaints,
        counts=counts,
        status_filter=status_filter,
    )


# ============================================================
# ADMIN: COMPLAINT DETAIL / REPLY
# ============================================================

@app.route("/admin/complaint/<tracking_code>", methods=["GET", "POST"])
@admin_required
def admin_complaint_detail(tracking_code):

    tracking_code = tracking_code.strip().upper()
    complaint, messages = get_complaint_thread(tracking_code)

    if not complaint:
        flash("Complaint not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":

        action = request.form.get("action")

        if action == "reply":

            message_text = request.form.get("message", "").strip()

            if not message_text:
                flash("Please write a reply before sending.", "error")
                return redirect(url_for("admin_complaint_detail", tracking_code=tracking_code))

            conn = get_db()

            try:
                with conn.cursor() as cur:

                    cur.execute(
                        """
                        INSERT INTO complaint_messages (complaint_id, sender_type, message)
                        VALUES (%s, 'admin', %s)
                        RETURNING id
                        """,
                        (complaint["id"], message_text),
                    )
                    message_id = cur.fetchone()["id"]

                    cur.execute(
                        "UPDATE complaints SET updated_at = NOW() WHERE id = %s",
                        (complaint["id"],),
                    )

                conn.commit()

            finally:
                conn.close()

            files = request.files.getlist("images")
            save_message_images(message_id, files, f"complaints/{tracking_code}")

        elif action == "set_status":

            new_status = request.form.get("status")

            if new_status in ("open", "in_progress", "resolved"):

                conn = get_db()

                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE complaints SET status = %s, updated_at = NOW() WHERE id = %s",
                            (new_status, complaint["id"]),
                        )
                    conn.commit()

                finally:
                    conn.close()

                flash(f"Status updated to {new_status.replace('_', ' ')}.", "success")

        return redirect(url_for("admin_complaint_detail", tracking_code=tracking_code))

    return render_template(
        "complaint_thread.html",
        complaint=complaint,
        messages=messages,
        is_admin_view=True,
    )


# ============================================================
# ADMIN: UPDATES (ANNOUNCEMENTS)
# ============================================================

@app.route("/admin/updates", methods=["GET", "POST"])
@admin_required
def admin_updates():

    if request.method == "POST":

        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()

        if not title or not body:
            flash("Please fill in both a title and body for the update.", "error")
            return redirect(url_for("admin_updates"))

        conn = get_db()

        try:
            with conn.cursor() as cur:

                cur.execute(
                    "INSERT INTO updates (title, body) VALUES (%s, %s) RETURNING id",
                    (title, body),
                )
                update_id = cur.fetchone()["id"]

                files = request.files.getlist("images")
                count = 0

                for file_storage in files:

                    if count >= MAX_IMAGES_PER_MESSAGE:
                        break

                    if not file_storage or not file_storage.filename:
                        continue

                    key = upload_image(file_storage, "updates")

                    if key:
                        cur.execute(
                            "INSERT INTO update_images (update_id, image_key) VALUES (%s, %s)",
                            (update_id, key),
                        )
                        count += 1

            conn.commit()

        finally:
            conn.close()

        flash("Update posted.", "success")
        return redirect(url_for("admin_updates"))

    conn = get_db()

    try:
        with conn.cursor() as cur:

            cur.execute("SELECT * FROM updates ORDER BY created_at DESC")
            updates = cur.fetchall()

            for update in updates:
                cur.execute(
                    "SELECT image_key FROM update_images WHERE update_id = %s",
                    (update["id"],),
                )
                update["image_urls"] = [
                    public_url(row["image_key"]) for row in cur.fetchall()
                ]

    finally:
        conn.close()

    return render_template("admin_updates.html", updates=updates)

@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():

    if request.method == "POST":

        company_name = request.form.get("company_name", "").strip()
        location = request.form.get("location", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()

        if not company_name:
            flash("Company name is required.", "error")
            return redirect(url_for("admin_settings"))

        settings = get_company_settings()

        logo_key = settings.get("logo_key")
        logo_file = request.files.get("logo")

        if logo_file and logo_file.filename:
            uploaded_key = upload_image(logo_file, "company_logo")

            if uploaded_key:
                logo_key = uploaded_key
            else:
                flash("Logo must be a PNG, JPG, GIF, or WEBP image.", "error")
                return redirect(url_for("admin_settings"))

        conn = get_db()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE company_settings
                    SET company_name = %s,
                        location = %s,
                        phone = %s,
                        email = %s,
                        logo_key = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (company_name, location, phone, email, logo_key, settings["id"]),
                )
            conn.commit()

        finally:
            conn.close()

        flash("Settings saved.", "success")
        return redirect(url_for("admin_settings"))

    settings = get_company_settings()
    return render_template("admin_settings.html", settings=settings)

if __name__ == "__main__":
    app.run(debug=True)
