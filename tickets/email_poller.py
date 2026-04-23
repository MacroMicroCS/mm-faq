"""IMAP polling — fetch new emails, create/thread tickets."""
import asyncio
import email
import email.header
import imaplib
import json
import logging
import re
import ssl
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

import bleach
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tickets.crypto import decrypt_value
from tickets.database import AsyncSessionLocal
from tickets.models import (
    Attachment, Customer, EmailAccount, Message, Ticket, TicketActivity,
)

log = logging.getLogger("ticket.poller")

UPLOAD_DIR = Path(__file__).parent.parent / "static" / "uploads" / "tickets"
POLL_INTERVAL = 60  # seconds

ALLOWED_HTML_TAGS = list(bleach.sanitizer.ALLOWED_TAGS) + [
    "p", "br", "div", "span", "pre", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "img", "ul", "ol", "li",
]
ALLOWED_HTML_ATTRS = {**bleach.sanitizer.ALLOWED_ATTRIBUTES, "img": ["src", "alt", "width", "height"], "a": ["href", "title"]}


async def poll_loop():
    """Background task: poll all active email accounts every POLL_INTERVAL seconds."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await poll_all_accounts(db)
        except Exception:
            log.exception("Poller cycle failed")
        await asyncio.sleep(POLL_INTERVAL)


async def poll_all_accounts(db: AsyncSession):
    result = await db.execute(select(EmailAccount).where(EmailAccount.is_active == True))
    accounts = result.scalars().all()
    for account in accounts:
        try:
            await asyncio.to_thread(_poll_account_sync, account, db)
        except Exception:
            log.exception(f"Failed polling account {account.id} ({account.label})")


def _poll_account_sync(account: EmailAccount, db: AsyncSession):
    """Synchronous IMAP fetch — runs in a thread via asyncio.to_thread."""
    password = decrypt_value(account.imap_password_enc)
    ctx = ssl.create_default_context()

    with imaplib.IMAP4_SSL(account.imap_host, account.imap_port, ssl_context=ctx) as imap:
        imap.login(account.imap_user, password)
        imap.select("INBOX")

        # Fetch UIDs greater than last processed
        uid_criterion = f"UID {account.last_uid + 1}:*"
        _, data = imap.uid("search", None, "ALL")
        all_uids = data[0].split()

        new_uids = [u for u in all_uids if int(u) > account.last_uid]
        if not new_uids:
            return

        for uid_bytes in new_uids:
            uid = int(uid_bytes)
            try:
                _, msg_data = imap.uid("fetch", uid_bytes, "(RFC822)")
                raw = msg_data[0][1]
                parsed = email.message_from_bytes(raw)
                asyncio.get_event_loop().run_until_complete(
                    _process_email(parsed, account, db)
                )
            except Exception:
                log.exception(f"Failed processing UID {uid}")
            account.last_uid = max(account.last_uid, uid)

        asyncio.get_event_loop().run_until_complete(db.commit())


async def _process_email(msg: email.message.Message, account: EmailAccount, db: AsyncSession):
    message_id = msg.get("Message-ID", "").strip()
    if not message_id:
        return

    # Deduplicate by Message-ID
    existing = await db.execute(
        select(Message).where(Message.email_message_id == message_id)
    )
    if existing.scalar_one_or_none():
        return

    from_name, from_email = parseaddr(msg.get("From", ""))
    from_email = from_email.lower().strip()
    if not from_email:
        return

    subject = _decode_header(msg.get("Subject", "(no subject)"))
    in_reply_to = msg.get("In-Reply-To", "").strip()
    references = msg.get("References", "").strip()
    body_html, body_text, attachments_data = _extract_body_and_attachments(msg)

    # Upsert customer
    customer = await _get_or_create_customer(from_email, from_name, db)

    # Find existing ticket via email threading (3-layer fallback)
    ticket = await _find_existing_ticket(in_reply_to, references, subject, customer, db)

    new_ticket_created = ticket is None
    if new_ticket_created:
        ticket = await _create_ticket(subject, customer, account, message_id, db)

    # Add message to ticket
    new_msg = Message(
        ticket_id=ticket.id,
        author_type="customer",
        author_id=customer.id,
        body_html=body_html,
        body_text=body_text,
        is_internal=False,
        is_draft=False,
        email_message_id=message_id,
        email_in_reply_to=in_reply_to or None,
        from_addr=from_email,
        to_addrs=json.dumps([account.smtp_user]),
        sent_at=_parse_date(msg.get("Date")),
    )
    db.add(new_msg)
    await db.flush()

    # Save attachments
    for att in attachments_data:
        _save_attachment(att, new_msg.id, db)

    # Mark ticket as updated
    ticket.updated_at = datetime.utcnow()
    if ticket.status == "solved":
        ticket.status = "open"  # reopen on customer reply

    db.add(TicketActivity(
        ticket_id=ticket.id,
        action="message_received",
        detail=json.dumps({"from": from_email, "message_id": message_id}),
    ))

    # Auto-reply for new tickets only
    if new_ticket_created:
        from tickets.auto_reply import send_auto_reply
        await send_auto_reply(ticket, customer, account, db)


async def _get_or_create_customer(email_addr: str, name: str, db: AsyncSession) -> Customer:
    result = await db.execute(
        select(Customer).where(Customer.email_lower == email_addr)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        customer = Customer(
            email=email_addr,
            email_lower=email_addr,
            name=name or None,
        )
        db.add(customer)
        await db.flush()
    elif name and not customer.name:
        customer.name = name
    return customer


async def _find_existing_ticket(
    in_reply_to: str, references: str, subject: str, customer: Customer, db: AsyncSession
) -> Ticket | None:
    # Layer 1: In-Reply-To header
    if in_reply_to:
        result = await db.execute(
            select(Ticket).where(Ticket.email_message_id == in_reply_to)
        )
        ticket = result.scalar_one_or_none()
        if ticket:
            return ticket

        # Also check messages table
        result = await db.execute(
            select(Message).where(Message.email_message_id == in_reply_to)
        )
        msg = result.scalar_one_or_none()
        if msg:
            result = await db.execute(select(Ticket).where(Ticket.id == msg.ticket_id))
            return result.scalar_one_or_none()

    # Layer 2: References header
    if references:
        for ref_id in reversed(references.split()):
            ref_id = ref_id.strip()
            result = await db.execute(
                select(Message).where(Message.email_message_id == ref_id)
            )
            msg = result.scalar_one_or_none()
            if msg:
                result = await db.execute(select(Ticket).where(Ticket.id == msg.ticket_id))
                return result.scalar_one_or_none()

    # Layer 3: Subject fuzzy match (strip Re:/Fwd:) for same customer
    clean_subject = re.sub(r'^(Re|Fwd|FW|回覆|转发)[:：]\s*', '', subject, flags=re.IGNORECASE).strip()
    if clean_subject and customer:
        result = await db.execute(
            select(Ticket)
            .where(Ticket.customer_id == customer.id)
            .where(Ticket.subject.ilike(f"%{clean_subject[:50]}%"))
            .where(Ticket.status != "closed")
            .order_by(Ticket.created_at.desc())
        )
        return result.scalars().first()

    return None


async def _create_ticket(
    subject: str, customer: Customer, account: EmailAccount, message_id: str, db: AsyncSession
) -> Ticket:
    # Atomic ticket number using MAX + 1
    from sqlalchemy import func, select as sa_select
    result = await db.execute(sa_select(func.max(Ticket.number)))
    max_num = result.scalar() or 999
    number = max_num + 1

    ticket = Ticket(
        number=number,
        subject=subject,
        status="open",
        priority="normal",
        channel="email",
        customer_id=customer.id,
        source_account_id=account.id,
        email_message_id=message_id,
        email_thread_id=message_id,
    )
    db.add(ticket)
    await db.flush()

    db.add(TicketActivity(ticket_id=ticket.id, action="created"))
    return ticket


def _extract_body_and_attachments(msg: email.message.Message):
    body_html = ""
    body_text = ""
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))

            if "attachment" in cd:
                attachments.append({
                    "filename": part.get_filename() or "attachment",
                    "content_type": ct,
                    "data": part.get_payload(decode=True),
                })
            elif ct == "text/html" and not body_html:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                body_html = bleach.clean(payload.decode(charset, errors="replace"), tags=ALLOWED_HTML_TAGS, attributes=ALLOWED_HTML_ATTRS)
            elif ct == "text/plain" and not body_text:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                body_text = payload.decode(charset, errors="replace")
    else:
        ct = msg.get_content_type()
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        decoded = payload.decode(charset, errors="replace")
        if ct == "text/html":
            body_html = bleach.clean(decoded, tags=ALLOWED_HTML_TAGS, attributes=ALLOWED_HTML_ATTRS)
        else:
            body_text = decoded

    if not body_html and body_text:
        body_html = "<pre>" + bleach.clean(body_text) + "</pre>"

    return body_html, body_text, attachments


def _save_attachment(att: dict, message_id: int, db: AsyncSession):
    import uuid
    ext = Path(att["filename"]).suffix or ".bin"
    filename = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / filename
    path.write_bytes(att["data"] or b"")

    attachment = Attachment(
        message_id=message_id,
        filename=att["filename"],
        content_type=att["content_type"],
        size_bytes=len(att["data"] or b""),
        storage_path=str(path),
    )
    db.add(attachment)


def _decode_header(value: str) -> str:
    parts = email.header.decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None
