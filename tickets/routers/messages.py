"""Message thread, draft save/discard, send reply, internal notes."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tickets.auth import get_current_agent
from tickets.database import get_db
from tickets.models import EmailAccount, Message, ReplyTemplate, Ticket, TicketActivity, TicketRead

router = APIRouter()


@router.post("/api/tickets/{ticket_id}/draft")
async def save_draft(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    """Save or update the agent's draft reply for this ticket."""
    body = await request.json()

    # Find existing draft by this agent
    result = await db.execute(
        select(Message).where(
            Message.ticket_id == ticket_id,
            Message.is_draft == True,
            Message.author_type == "agent",
            Message.author_id == agent.id,
        )
    )
    draft = result.scalar_one_or_none()

    if draft:
        draft.body_html = body.get("body_html", draft.body_html)
        draft.to_addrs = json.dumps(body.get("to_addrs", []))
        draft.cc_addrs = json.dumps(body.get("cc_addrs", []))
        draft.bcc_addrs = json.dumps(body.get("bcc_addrs", []))
    else:
        draft = Message(
            ticket_id=ticket_id,
            author_type="agent",
            author_id=agent.id,
            body_html=body.get("body_html", ""),
            is_draft=True,
            is_internal=body.get("is_internal", False),
            to_addrs=json.dumps(body.get("to_addrs", [])),
            cc_addrs=json.dumps(body.get("cc_addrs", [])),
            bcc_addrs=json.dumps(body.get("bcc_addrs", [])),
            template_id=body.get("template_id"),
            template_variables=json.dumps(body.get("template_variables", {})) if body.get("template_variables") else None,
        )
        db.add(draft)

    await db.commit()
    return {"ok": True, "draft_id": draft.id}


@router.delete("/api/tickets/{ticket_id}/draft")
async def discard_draft(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    result = await db.execute(
        select(Message).where(
            Message.ticket_id == ticket_id,
            Message.is_draft == True,
            Message.author_id == agent.id,
        )
    )
    draft = result.scalar_one_or_none()
    if draft:
        await db.delete(draft)
        await db.commit()
    return {"ok": True}


@router.post("/api/tickets/{ticket_id}/send")
async def send_reply(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    is_internal = body.get("is_internal", False)
    body_html = body.get("body_html", "").strip()
    if not body_html:
        raise HTTPException(status_code=400, detail="Body is empty")

    # Get ticket with customer
    result = await db.execute(
        select(Ticket).options(selectinload(Ticket.customer)).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404)

    sent_at = None
    email_message_id = None

    if not is_internal:
        # Load email account for sending
        if ticket.source_account_id:
            acc_result = await db.execute(
                select(EmailAccount).where(EmailAccount.id == ticket.source_account_id)
            )
            account = acc_result.scalar_one_or_none()
        else:
            acc_result = await db.execute(
                select(EmailAccount).where(EmailAccount.is_active == True).limit(1)
            )
            account = acc_result.scalar_one_or_none()

        if not account:
            raise HTTPException(status_code=400, detail="No email account configured")

        to_addrs = body.get("to_addrs") or [ticket.customer.email]
        cc_addrs = body.get("cc_addrs", [])
        bcc_addrs = body.get("bcc_addrs", [])

        from tickets.email_sender import send_reply as smtp_send
        email_message_id = await smtp_send(
            account=account,
            to_addrs=to_addrs,
            subject=f"Re: {ticket.subject}",
            body_html=body_html,
            body_text=body.get("body_text", ""),
            cc_addrs=cc_addrs or None,
            bcc_addrs=bcc_addrs or None,
            in_reply_to=ticket.email_message_id,
            references=ticket.email_thread_id,
        )
        sent_at = datetime.utcnow()

        # Track first response time
        if not ticket.first_response_at:
            ticket.first_response_at = sent_at
            ticket.sla_first_responded_at = sent_at

    # Save as sent message
    msg = Message(
        ticket_id=ticket_id,
        author_type="agent",
        author_id=agent.id,
        body_html=body_html,
        body_text=body.get("body_text", ""),
        is_internal=is_internal,
        is_draft=False,
        email_message_id=email_message_id,
        email_in_reply_to=ticket.email_message_id,
        to_addrs=json.dumps(body.get("to_addrs", [])),
        cc_addrs=json.dumps(body.get("cc_addrs", [])),
        bcc_addrs=json.dumps(body.get("bcc_addrs", [])),
        template_id=body.get("template_id"),
        ai_generated=body.get("ai_generated", False),
        sent_at=sent_at,
    )
    db.add(msg)

    # Remove draft if exists
    draft_result = await db.execute(
        select(Message).where(
            Message.ticket_id == ticket_id,
            Message.is_draft == True,
            Message.author_id == agent.id,
        )
    )
    draft = draft_result.scalar_one_or_none()
    if draft:
        await db.delete(draft)

    if not is_internal:
        ticket.status = body.get("new_status", ticket.status)
    ticket.updated_at = datetime.utcnow()

    db.add(TicketActivity(
        ticket_id=ticket_id, agent_id=agent.id,
        action="internal_note_added" if is_internal else "replied",
    ))

    # Invalidate read status for other agents
    result = await db.execute(
        select(TicketRead).where(TicketRead.ticket_id == ticket_id, TicketRead.agent_id != agent.id)
    )
    for tr in result.scalars().all():
        await db.delete(tr)

    await db.commit()
    return {"ok": True, "message_id": msg.id}


@router.get("/api/tickets/{ticket_id}/draft")
async def get_draft(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    result = await db.execute(
        select(Message).where(
            Message.ticket_id == ticket_id,
            Message.is_draft == True,
            Message.author_id == agent.id,
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        return {"draft": None}
    return {
        "draft": {
            "id": draft.id,
            "body_html": draft.body_html,
            "to_addrs": json.loads(draft.to_addrs or "[]"),
            "cc_addrs": json.loads(draft.cc_addrs or "[]"),
            "bcc_addrs": json.loads(draft.bcc_addrs or "[]"),
            "template_id": draft.template_id,
        }
    }
