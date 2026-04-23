"""Auto-reply: send acknowledgment email when a new ticket is created from email."""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tickets.models import Customer, EmailAccount, Message, Ticket

log = logging.getLogger("ticket.auto_reply")

AUTO_REPLY_SUBJECT = {
    "zh-tw": "我們已收到您的來信 [#{number}]",
    "zh-cn": "我们已收到您的来信 [#{number}]",
    "en": "We received your message [#{number}]",
}

AUTO_REPLY_BODY = {
    "zh-tw": """<p>您好，</p>
<p>感謝您聯絡 MacroMicro 客服，我們已收到您的來信，並已建立服務單號 <strong>#{number}</strong>。</p>
<p>我們的客服團隊將在工作時間內盡快回覆您，請稍待耐心等候。</p>
<p>如有緊急問題，請直接回覆此郵件。</p>
<br>
<p>MacroMicro 客服團隊</p>""",

    "zh-cn": """<p>您好，</p>
<p>感谢您联系 MacroMicro 客服，我们已收到您的来信，并已建立服务单号 <strong>#{number}</strong>。</p>
<p>我们的客服团队将在工作时间内尽快回复您，请稍等。</p>
<br>
<p>MacroMicro 客服团队</p>""",

    "en": """<p>Hello,</p>
<p>Thank you for contacting MacroMicro support. We have received your message and created ticket <strong>#{number}</strong>.</p>
<p>Our team will respond during business hours as soon as possible.</p>
<br>
<p>MacroMicro Support Team</p>""",
}


async def send_auto_reply(ticket: Ticket, customer: Customer, account: EmailAccount, db: AsyncSession):
    """Send auto-reply acknowledgment for new email tickets."""
    locale = customer.locale or "zh-tw"
    subject = AUTO_REPLY_SUBJECT.get(locale, AUTO_REPLY_SUBJECT["zh-tw"]).replace("{number}", str(ticket.number))
    body = AUTO_REPLY_BODY.get(locale, AUTO_REPLY_BODY["zh-tw"]).replace("{number}", str(ticket.number))

    try:
        from tickets.email_sender import send_reply
        import json
        from datetime import datetime

        msg_id = await send_reply(
            account=account,
            to_addrs=[customer.email],
            subject=subject,
            body_html=body,
            in_reply_to=ticket.email_message_id,
            references=ticket.email_thread_id,
        )

        db.add(Message(
            ticket_id=ticket.id,
            author_type="system",
            body_html=body,
            is_internal=False,
            is_draft=False,
            email_message_id=msg_id,
            from_addr=account.smtp_user,
            to_addrs=json.dumps([customer.email]),
            sent_at=datetime.utcnow(),
        ))
        await db.flush()
        log.info(f"Auto-reply sent for ticket #{ticket.number} to {customer.email}")
    except Exception:
        log.exception(f"Failed to send auto-reply for ticket #{ticket.number}")
