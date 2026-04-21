"""Ticket CRUD, status, assign, bulk actions, collision detection."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tickets.auth import get_current_agent
from tickets.collision import get_viewers, heartbeat, leave
from tickets.database import get_db
from tickets.models import Agent, Customer, Tag, Ticket, TicketActivity, TicketRead, TicketTag

router = APIRouter()

STATUS_LABELS = {
    "open": "待處理",
    "pending": "等待回覆",
    "solved": "已解決",
    "closed": "已關閉",
}
PRIORITY_LABELS = {
    "low": "低",
    "normal": "普通",
    "high": "高",
    "urgent": "緊急",
}


@router.get("/inbox", response_class=HTMLResponse)
async def inbox(
    request: Request,
    status: str = "open",
    priority: str = "",
    assigned: str = "",
    page: int = 1,
    q: str = "",
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    from tickets.app import templates

    per_page = 25
    query = (
        select(Ticket)
        .options(selectinload(Ticket.customer), selectinload(Ticket.tags).selectinload(TicketTag.tag))
        .order_by(Ticket.updated_at.desc().nullslast(), Ticket.created_at.desc())
    )

    if status:
        query = query.where(Ticket.status == status)
    if priority:
        query = query.where(Ticket.priority == priority)
    if assigned == "me":
        query = query.where(Ticket.assigned_agent_id == agent.id)
    elif assigned == "unassigned":
        query = query.where(Ticket.assigned_agent_id == None)
    if q:
        query = query.where(Ticket.subject.ilike(f"%{q}%"))
    query = query.where(Ticket.merged_into_id == None)

    # Count total
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    tickets = (await db.execute(query.offset((page - 1) * per_page).limit(per_page))).scalars().all()

    # Unread status per ticket
    read_result = await db.execute(
        select(TicketRead.ticket_id).where(TicketRead.agent_id == agent.id)
    )
    read_ids = set(read_result.scalars().all())

    # All agents for assign dropdown
    agents_result = await db.execute(select(Agent).where(Agent.is_active == True))
    all_agents = agents_result.scalars().all()

    return templates.TemplateResponse(request, "tickets/inbox.html", {
        "tickets": tickets,
        "agent": agent,
        "all_agents": all_agents,
        "read_ids": read_ids,
        "status_filter": status,
        "priority_filter": priority,
        "assigned_filter": assigned,
        "q": q,
        "page": page,
        "total": total,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "status_labels": STATUS_LABELS,
        "priority_labels": PRIORITY_LABELS,
    })


@router.get("/{ticket_id}", response_class=HTMLResponse)
async def ticket_detail(
    request: Request,
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    from tickets.app import templates

    result = await db.execute(
        select(Ticket)
        .options(
            selectinload(Ticket.customer),
            selectinload(Ticket.messages),
            selectinload(Ticket.tags).selectinload(TicketTag.tag),
            selectinload(Ticket.activity),
        )
        .where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404)

    # Mark as read
    existing_read = await db.execute(
        select(TicketRead).where(TicketRead.ticket_id == ticket_id, TicketRead.agent_id == agent.id)
    )
    if not existing_read.scalar_one_or_none():
        db.add(TicketRead(ticket_id=ticket_id, agent_id=agent.id))
        await db.commit()

    # All agents for assign
    agents_result = await db.execute(select(Agent).where(Agent.is_active == True))
    all_agents = agents_result.scalars().all()

    # All tags
    tags_result = await db.execute(select(Tag))
    all_tags = tags_result.scalars().all()
    ticket_tag_ids = {tt.tag_id for tt in ticket.tags}

    return templates.TemplateResponse(request, "tickets/ticket_detail.html", {
        "ticket": ticket,
        "agent": agent,
        "all_agents": all_agents,
        "all_tags": all_tags,
        "ticket_tag_ids": ticket_tag_ids,
        "status_labels": STATUS_LABELS,
        "priority_labels": PRIORITY_LABELS,
    })


# ── API endpoints ──────────────────────────────────────────────────────────────

@router.post("/api/tickets/{ticket_id}/status")
async def update_status(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    new_status = body.get("status")
    if new_status not in STATUS_LABELS:
        raise HTTPException(status_code=400, detail="Invalid status")

    ticket = await _get_ticket(ticket_id, db)
    old_status = ticket.status
    ticket.status = new_status
    if new_status == "solved" and not ticket.solved_at:
        ticket.solved_at = datetime.utcnow()
    elif new_status == "closed" and not ticket.closed_at:
        ticket.closed_at = datetime.utcnow()

    db.add(TicketActivity(
        ticket_id=ticket_id, agent_id=agent.id, action="status_changed",
        field_name="status", old_value=old_status, new_value=new_status,
    ))
    await db.commit()
    return {"ok": True, "status": new_status}


@router.post("/api/tickets/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    new_agent_id = body.get("agent_id")

    ticket = await _get_ticket(ticket_id, db)
    old = ticket.assigned_agent_id
    ticket.assigned_agent_id = new_agent_id or None

    db.add(TicketActivity(
        ticket_id=ticket_id, agent_id=agent.id, action="assigned",
        field_name="assigned_agent_id",
        old_value=str(old) if old else None,
        new_value=str(new_agent_id) if new_agent_id else None,
    ))
    await db.commit()
    return {"ok": True}


@router.post("/api/tickets/{ticket_id}/priority")
async def update_priority(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    new_priority = body.get("priority")
    if new_priority not in PRIORITY_LABELS:
        raise HTTPException(status_code=400, detail="Invalid priority")

    ticket = await _get_ticket(ticket_id, db)
    old = ticket.priority
    ticket.priority = new_priority
    db.add(TicketActivity(
        ticket_id=ticket_id, agent_id=agent.id, action="priority_changed",
        field_name="priority", old_value=old, new_value=new_priority,
    ))
    await db.commit()
    return {"ok": True}


@router.post("/api/tickets/{ticket_id}/tags")
async def update_tags(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    tag_ids = body.get("tag_ids", [])

    ticket = await _get_ticket(ticket_id, db)
    result = await db.execute(select(TicketTag).where(TicketTag.ticket_id == ticket_id))
    for tt in result.scalars().all():
        await db.delete(tt)
    for tid in tag_ids:
        db.add(TicketTag(ticket_id=ticket_id, tag_id=tid))
    await db.commit()
    return {"ok": True}


@router.post("/api/tickets/{ticket_id}/merge")
async def merge_ticket(
    ticket_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    target_id = body.get("target_ticket_id")
    if not target_id or target_id == ticket_id:
        raise HTTPException(status_code=400, detail="Invalid target")

    ticket = await _get_ticket(ticket_id, db)
    ticket.merged_into_id = target_id
    ticket.status = "closed"
    ticket.closed_at = datetime.utcnow()
    db.add(TicketActivity(
        ticket_id=ticket_id, agent_id=agent.id, action="merged",
        detail=json.dumps({"merged_into": target_id}),
    ))
    await db.commit()
    return {"ok": True}


@router.post("/api/tickets/bulk")
async def bulk_action(
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    ticket_ids = body.get("ticket_ids", [])
    action = body.get("action")
    value = body.get("value")

    if not ticket_ids or not action:
        raise HTTPException(status_code=400, detail="Missing ticket_ids or action")

    result = await db.execute(select(Ticket).where(Ticket.id.in_(ticket_ids)))
    tickets = result.scalars().all()

    for ticket in tickets:
        if action == "status" and value in STATUS_LABELS:
            ticket.status = value
        elif action == "priority" and value in PRIORITY_LABELS:
            ticket.priority = value
        elif action == "assign":
            ticket.assigned_agent_id = int(value) if value else None
        db.add(TicketActivity(ticket_id=ticket.id, agent_id=agent.id, action=f"bulk_{action}", new_value=str(value)))

    await db.commit()
    return {"ok": True, "updated": len(tickets)}


@router.post("/api/tickets/{ticket_id}/presence")
async def presence_heartbeat(
    ticket_id: int,
    agent=Depends(get_current_agent),
):
    heartbeat(ticket_id, agent.id, agent.name)
    return {"ok": True}


@router.get("/api/tickets/{ticket_id}/presence")
async def get_presence(
    ticket_id: int,
    agent=Depends(get_current_agent),
):
    return {"viewers": get_viewers(ticket_id, exclude_agent_id=agent.id)}


@router.post("/api/tickets/new")
async def create_ticket_manual(
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    email_addr = (body.get("customer_email") or "").lower().strip()
    if not email_addr:
        raise HTTPException(status_code=400, detail="customer_email required")

    result = await db.execute(
        select(Customer).where(Customer.email_lower == email_addr)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        customer = Customer(
            email=email_addr,
            email_lower=email_addr,
            name=body.get("customer_name") or None,
        )
        db.add(customer)
        await db.flush()

    count_result = await db.execute(select(func.max(Ticket.number)))
    number = (count_result.scalar() or 999) + 1

    ticket = Ticket(
        number=number,
        subject=body.get("subject", "(no subject)"),
        status="open",
        priority=body.get("priority", "normal"),
        channel="manual",
        customer_id=customer.id,
        assigned_agent_id=agent.id,
    )
    db.add(ticket)
    await db.flush()
    db.add(TicketActivity(ticket_id=ticket.id, agent_id=agent.id, action="created"))
    await db.commit()
    return {"ok": True, "ticket_id": ticket.id, "ticket_number": ticket.number}


async def _get_ticket(ticket_id: int, db: AsyncSession) -> Ticket:
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404)
    return ticket
