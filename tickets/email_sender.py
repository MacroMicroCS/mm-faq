"""SMTP email sending with proper thread headers."""
import asyncio
import json
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from pathlib import Path

from tickets.crypto import decrypt_value


async def send_reply(
    account,
    to_addrs: list[str],
    subject: str,
    body_html: str,
    body_text: str = "",
    cc_addrs: list[str] | None = None,
    bcc_addrs: list[str] | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> str:
    """Send an email and return the generated Message-ID."""
    msg_id = make_msgid(domain=account.smtp_user.split("@")[-1])

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((account.label, account.smtp_user))
    msg["To"] = ", ".join(to_addrs)
    msg["Message-ID"] = msg_id

    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    password = decrypt_value(account.smtp_password_enc)
    all_recipients = list(to_addrs) + (cc_addrs or []) + (bcc_addrs or [])

    await asyncio.to_thread(_smtp_send, account, password, all_recipients, msg)
    return msg_id


def _smtp_send(account, password: str, recipients: list[str], msg: MIMEMultipart):
    context = ssl.create_default_context()
    if account.smtp_port == 465:
        with smtplib.SMTP_SSL(account.smtp_host, account.smtp_port, context=context) as smtp:
            smtp.login(account.smtp_user, password)
            smtp.sendmail(account.smtp_user, recipients, msg.as_string())
    else:
        with smtplib.SMTP(account.smtp_host, account.smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.login(account.smtp_user, password)
            smtp.sendmail(account.smtp_user, recipients, msg.as_string())
