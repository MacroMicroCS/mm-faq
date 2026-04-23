"""Customer profile — list, detail with ticket history, notes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tickets.auth import get_current_agent
from tickets.database import get_db
from tickets.models import Customer, Ticket

router = APIRouter()


@router.get("/customers", response_class=HTMLResponse)
async def customers_list(
    request: Request,
    q: str = "",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    from tickets.app import templates

    per_page = 30
    query = select(Customer).order_by(Customer.created_at.desc())
    if q:
        query = query.where(
            Customer.email_lower.ilike(f"%{q.lower()}%") |
            Customer.name.ilike(f"%{q}%")
        )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    customers = (await db.execute(query.offset((page - 1) * per_page).limit(per_page))).scalars().all()

    # Ticket counts per customer
    cids = [c.id for c in customers]
    counts = {}
    if cids:
        result = await db.execute(
            select(Ticket.customer_id, func.count(Ticket.id))
            .where(Ticket.customer_id.in_(cids))
            .group_by(Ticket.customer_id)
        )
        counts = dict(result.all())

    return templates.TemplateResponse(request, "tickets/customers.html", {
        "customers": customers,
        "counts": counts,
        "agent": agent,
        "q": q,
        "page": page,
        "total": total,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


@router.get("/customers/{customer_id}", response_class=HTMLResponse)
async def customer_detail(
    request: Request,
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    from tickets.app import templates

    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404)

    tickets_result = await db.execute(
        select(Ticket)
        .where(Ticket.customer_id == customer_id)
        .order_by(Ticket.created_at.desc())
    )
    tickets = tickets_result.scalars().all()

    return templates.TemplateResponse(request, "tickets/customer_detail.html", {
        "customer": customer,
        "tickets": tickets,
        "agent": agent,
    })


@router.post("/api/customers/{customer_id}/notes")
async def update_customer_notes(
    customer_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404)
    customer.notes = body.get("notes", "")
    await db.commit()
    return {"ok": True}
