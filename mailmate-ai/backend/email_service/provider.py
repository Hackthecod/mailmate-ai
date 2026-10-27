"""Gmail IMAP search/read helpers and SMTP sending for MailMate AI.

Uses a Gmail App Password. Inbox tools are read-only; sending is only called by
 the separate human-approval service.
"""
from __future__ import annotations

import email
import imaplib
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from typing import Any

from backend.config import settings

IMAP_HOST = "imap.gmail.com"
SMTP_HOST = "smtp.gmail.com"


def _credentials() -> tuple[str, str]:
    address = settings.gmail_address.strip()
    password = settings.gmail_app_password.replace(" ", "").strip()
    if not address or not password:
        raise RuntimeError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be configured in backend/.env.")
    return address, password


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(value)).strip()


def _part_text(part: email.message.Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _message_body(msg: email.message.Message) -> str:
    plain: list[str] = []
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                continue
            content_type = part.get_content_type()
            if content_type == "text/plain":
                plain.append(_part_text(part))
            elif content_type == "text/html":
                html_parts.append(_part_text(part))
    else:
        content = _part_text(msg)
        if msg.get_content_type() == "text/html":
            html_parts.append(content)
        else:
            plain.append(content)
    body = "\n".join(plain).strip() or _html_to_text(" ".join(html_parts))
    return re.sub(r"\s+", " ", body).strip()


def _date_string(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return raw


def _parse_message(uid: str, raw: bytes, include_body: bool = False) -> dict[str, Any]:
    msg = email.message_from_bytes(raw)
    sender_name, sender_email = parseaddr(_decode_header(msg.get("From")))
    body = _message_body(msg)
    result = {
        "email_id": str(uid),
        "sender_name": sender_name,
        "sender_email": sender_email,
        "to": _decode_header(msg.get("To")),
        "subject": _decode_header(msg.get("Subject")) or "(no subject)",
        "date": _date_string(msg.get("Date")),
        "snippet": body[:280],
    }
    if include_body:
        result["body"] = body[:20000]
    return result


def _fetch_messages(limit: int = 20, since_days: int | None = 30) -> list[dict[str, Any]]:
    address, password = _credentials()
    limit = max(1, min(int(limit), 50))
    with imaplib.IMAP4_SSL(IMAP_HOST) as client:
        client.login(address, password)
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError("Could not open Gmail INBOX.")
        status, data = client.uid("search", None, "ALL")
        if status != "OK" or not data or not data[0]:
            return []
        uids = data[0].split()[-limit:][::-1]
        results: list[dict[str, Any]] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days) if since_days is not None else None
        for uid_bytes in uids:
            uid = uid_bytes.decode("ascii", errors="ignore")
            status, fetched = client.uid("fetch", uid, "(RFC822)")
            if status != "OK":
                continue
            raw = next((item[1] for item in fetched if isinstance(item, tuple) and isinstance(item[1], bytes)), None)
            if raw is None:
                continue
            item = _parse_message(uid, raw)
            if cutoff and item["date"]:
                try:
                    dt = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
                    if dt < cutoff:
                        continue
                except ValueError:
                    pass
            results.append(item)
    return results


def search_emails(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search recent inbox messages locally by subject, sender, and body text."""
    query = query.strip().lower()
    if not query:
        raise ValueError("Provide a keyword, sender, or subject to search for.")
    messages = _fetch_messages(limit=50, since_days=90)
    matches = []
    for item in messages:
        haystack = " ".join([item["subject"], item["sender_name"], item["sender_email"], item["snippet"]]).lower()
        if query in haystack:
            matches.append(item)
            if len(matches) >= max(1, min(int(limit), 20)):
                break
    return matches


def read_email(email_id: str) -> dict[str, Any]:
    """Read one message by its numeric Gmail INBOX UID returned by search_emails."""
    uid = email_id.strip()
    if not uid.isdigit():
        raise ValueError("email_id must be the numeric email_id returned by search_emails.")
    address, password = _credentials()
    with imaplib.IMAP4_SSL(IMAP_HOST) as client:
        client.login(address, password)
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError("Could not open Gmail INBOX.")
        status, fetched = client.uid("fetch", uid, "(RFC822)")
        if status != "OK":
            raise LookupError(f"Email {uid} could not be fetched.")
        raw = next((item[1] for item in fetched if isinstance(item, tuple) and isinstance(item[1], bytes)), None)
        if raw is None:
            raise LookupError(f"Email {uid} was not found in the INBOX.")
        return _parse_message(uid, raw, include_body=True)


def get_emails_from_sender(sender: str, limit: int = 10) -> list[dict[str, Any]]:
    """Find recent emails from a sender name or email address."""
    sender = sender.strip().lower()
    if not sender:
        raise ValueError("Provide a sender name or email address.")
    messages = _fetch_messages(limit=50, since_days=90)
    matches = [m for m in messages if sender in m["sender_email"].lower() or sender in m["sender_name"].lower()]
    return matches[:max(1, min(int(limit), 20))]


def get_important_recent_emails(limit: int = 10) -> list[dict[str, Any]]:
    """Rank recent emails using transparent urgency/action keyword heuristics."""
    messages = _fetch_messages(limit=50, since_days=14)
    urgent_terms = ("urgent", "action required", "deadline", "due today", "asap", "important", "payment", "invoice", "interview", "meeting", "approval", "follow up", "follow-up", "reminder")
    for item in messages:
        text = f"{item['subject']} {item['snippet']}".lower()
        item["importance_score"] = sum(2 if term in text else 0 for term in urgent_terms)
        if "urgent" in text or "action required" in text or "deadline" in text:
            item["importance_score"] += 3
    messages.sort(key=lambda m: (m["importance_score"], m["date"]), reverse=True)
    return messages[:max(1, min(int(limit), 20))]


def send_mail(recipient_email: str, subject: str, body: str) -> str:
    sender, app_password = _credentials()
    parsed = parseaddr(recipient_email)[1]
    if parsed != recipient_email or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", parsed):
        raise ValueError("Recipient email address is invalid.")
    if not subject.strip() or not body.strip():
        raise ValueError("Subject and body cannot be empty.")
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient_email
    with smtplib.SMTP(SMTP_HOST, 587, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, app_password)
        server.send_message(msg)
    return "Email sent successfully."
