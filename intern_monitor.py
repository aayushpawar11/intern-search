#!/usr/bin/env python3
"""
Intern role monitor.

Polls public company career boards on a 5-minute schedule, stores seen
postings in SQLite, and emails you when a new intern/SWE listing appears.

Usage:
  python intern_monitor.py --once --dry-run   # first-time test, no email
  python intern_monitor.py --once             # one pass, send email for new jobs
  python intern_monitor.py                    # run forever, check every 20 minutes
"""

from __future__ import annotations

import argparse
import logging
import os
import smtplib
import sqlite3
import ssl
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from companies import enabled_companies
from fetchers import JobPosting, check_company
from http_client import RateLimitedSession

load_dotenv()

# =============================================================================
# CONFIG — edit here, or set the matching env vars in a .env file
# =============================================================================

CHECK_INTERVAL_MINUTES = 20
REQUEST_DELAY_SECONDS = 1.8
HTTP_TIMEOUT_SECONDS = 25.0

# On the first run (empty DB) record current listings without emailing them.
# That way you only get alerts for jobs that appear *after* you start monitoring.
SEED_ON_EMPTY_DB = True

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "seen_jobs.db"
LOG_PATH = DATA_DIR / "intern_monitor.log"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_FROM = os.getenv("ALERT_FROM", "") or SMTP_USERNAME
ALERT_TO = os.getenv("ALERT_TO", "")

logger = logging.getLogger("intern_monitor")


def setup_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


def connect_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_jobs (
            fingerprint TEXT PRIMARY KEY,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            posted_date TEXT,
            location TEXT,
            details TEXT,
            first_seen TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS check_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            companies_ok INTEGER DEFAULT 0,
            companies_failed INTEGER DEFAULT 0,
            new_jobs INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    return conn


def seen_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()
    return int(row[0]) if row else 0


def is_new(conn: sqlite3.Connection, job: JobPosting) -> bool:
    row = conn.execute(
        "SELECT 1 FROM seen_jobs WHERE fingerprint = ?",
        (job.fingerprint(),),
    ).fetchone()
    return row is None


def store_job(conn: sqlite3.Connection, job: JobPosting) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT OR IGNORE INTO seen_jobs
        (fingerprint, company, title, url, posted_date, location, details, first_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job.fingerprint(),
            job.company,
            job.title,
            job.url,
            job.posted_date,
            job.location,
            job.details,
            now,
        ),
    )


def email_configured() -> bool:
    return bool(SMTP_USERNAME and SMTP_PASSWORD and ALERT_TO)


def send_email_alerts(jobs: list[JobPosting]) -> None:
    if not jobs:
        return
    if not email_configured():
        logger.warning(
            "Email is not configured (SMTP_USERNAME / SMTP_PASSWORD / ALERT_TO). "
            "Printing %s new job(s) instead.",
            len(jobs),
        )
        for job in jobs:
            logger.info("NEW  %s | %s | %s", job.company, job.title, job.url)
        return

    subject = f"{len(jobs)} new intern/SWE posting{'s' if len(jobs) != 1 else ''}"
    lines = [
        f"<p>{len(jobs)} new intern/SWE role(s) detected.</p>",
        "<ul>",
    ]
    text_lines = [f"{len(jobs)} new intern/SWE role(s) detected:", ""]
    for job in jobs:
        lines.append(
            "<li>"
            f"<strong>{_escape(job.company)}</strong> — {_escape(job.title)}<br>"
            f"Posted: {_escape(job.posted_date or 'unknown')} · "
            f"Location: {_escape(job.location or 'n/a')}<br>"
            f"<a href='{_escape(job.url)}'>{_escape(job.url)}</a><br>"
            f"<em>{_escape(job.details)}</em>"
            "</li>"
        )
        text_lines.append(f"- [{job.company}] {job.title}")
        text_lines.append(f"  {job.url}")
        text_lines.append(f"  {job.posted_date} | {job.location}")
        text_lines.append("")

    lines.append("</ul>")
    html = "\n".join(lines)
    text = "\n".join(text_lines)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = ALERT_FROM
    msg["To"] = ALERT_TO
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls(context=context)
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(ALERT_FROM, [addr.strip() for addr in ALERT_TO.split(",")], msg.as_string())
    logger.info("Sent alert email for %s new job(s) to %s", len(jobs), ALERT_TO)


def _escape(value: str) -> str:
    return (
        (value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def run_check(
    *,
    dry_run: bool = False,
    only_company: str | None = None,
    force_seed: bool = False,
) -> None:
    companies = enabled_companies()
    if only_company:
        needle = only_company.lower()
        companies = [c for c in companies if needle in c.name.lower()]
        if not companies:
            logger.error("No enabled company matching %r", only_company)
            return

    http = RateLimitedSession(min_delay=REQUEST_DELAY_SECONDS, timeout=HTTP_TIMEOUT_SECONDS)
    conn = connect_db()
    started = datetime.now(timezone.utc).isoformat()
    empty_db = seen_count(conn) == 0
    seed_mode = force_seed or (SEED_ON_EMPTY_DB and empty_db)

    if seed_mode:
        logger.info("Seeding database with current listings (no alert emails this pass).")

    ok = 0
    failed = 0
    new_jobs: list[JobPosting] = []

    for company in companies:
        logger.info("Checking %s (%s)", company.name, company.source)
        try:
            jobs = check_company(http, company)
            ok += 1
        except Exception:
            logger.exception("Unhandled error for %s", company.name)
            failed += 1
            continue

        for job in jobs:
            if is_new(conn, job):
                if not seed_mode:
                    new_jobs.append(job)
                store_job(conn, job)

        conn.commit()

    finished = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO check_runs (started_at, finished_at, companies_ok, companies_failed, new_jobs)
        VALUES (?, ?, ?, ?, ?)
        """,
        (started, finished, ok, failed, 0 if seed_mode else len(new_jobs)),
    )
    conn.commit()
    conn.close()

    logger.info(
        "Pass complete: %s ok, %s failed, %s new intern/SWE jobs%s",
        ok,
        failed,
        0 if seed_mode else len(new_jobs),
        " (seeded)" if seed_mode else "",
    )

    if seed_mode or not new_jobs:
        return
    if dry_run:
        logger.info("Dry run — would email %s job(s):", len(new_jobs))
        for job in new_jobs:
            logger.info("NEW  %s | %s | %s", job.company, job.title, job.url)
        return
    send_email_alerts(new_jobs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor intern/SWE postings and email new ones.")
    parser.add_argument("--once", action="store_true", help="Run a single check and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Do not send email; log new jobs.")
    parser.add_argument("--company", help="Only check companies whose name contains this string.")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Record current listings without sending alerts.",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()
    companies = enabled_companies()
    logger.info(
        "Intern monitor starting with %s enabled companies; interval=%s min",
        len(companies),
        CHECK_INTERVAL_MINUTES,
    )

    if args.once or args.company or args.seed:
        run_check(dry_run=args.dry_run, only_company=args.company, force_seed=args.seed)
        return

    # Run immediately, then every CHECK_INTERVAL_MINUTES.
    run_check(dry_run=args.dry_run)
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_check,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        kwargs={"dry_run": args.dry_run},
        max_instances=1,
        coalesce=True,
        id="intern_check",
    )
    logger.info("Scheduler armed. Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down.")


if __name__ == "__main__":
    main()
