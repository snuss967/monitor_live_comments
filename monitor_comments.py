#!/usr/bin/env python3
"""
Poll a web page and alert when a “document comments” box appears.

Required secrets (set in the workflow-level env):
  WEBSITE_URL      – URL of the Regulations.gov document page
  EMAIL_USER       – full Gmail address (or any SMTP login)
  EMAIL_PASSWORD   – Gmail App-Password (or SMTP password)
  RECIPIENT        – destination address for the alert
"""
from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import requests
from bs4 import BeautifulSoup


STATE_FILE = Path("state.json")        # persisted across runs via actions/cache
PATTERN = re.compile(r"document\s+comments", re.I)   # insensitive search


def page_has_comments(html: str) -> bool:
    """Return True if the comments box is present."""
    soup = BeautifulSoup(html, "html.parser")
    # Fast check on raw HTML first (good enough and cheap).
    if PATTERN.search(html):
        return True
    # Fallback: look for any element that *looks* like the box.
    return bool(soup.select_one("[data-test-id='document-comments'], .document-comments"))


def fetch_html(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def load_previous_state() -> bool | None:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return None


def save_state(state: bool) -> None:
    STATE_FILE.write_text(json.dumps(state))


def send_email(subject: str, body: str) -> None:
    msg = EmailMessage()
    user, pwd, to_addr = map(os.getenv, ("EMAIL_USER", "EMAIL_PASSWORD", "RECIPIENT"))
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(user, pwd)
        s.send_message(msg)

    print("Notification sent to", to_addr)


def main() -> None:
    html = fetch_html(os.environ["WEBSITE_URL"])
    now_has_box = page_has_comments(html)
    prev = load_previous_state()

    # Only alert on the transition “absent → present”
    if prev is False and now_has_box is True:
        send_email(
            "🎉 Document comments box detected",
            f"The comments box just appeared on {os.environ['WEBSITE_URL']}.",
        )

    # Save the current observation for the next run
    save_state(now_has_box)
    print("Previous:", prev, "| Current:", now_has_box)


if __name__ == "__main__":
    main()
