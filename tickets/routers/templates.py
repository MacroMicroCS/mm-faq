"""Reply template CRUD, fuzzy search, variable preview."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tickets.auth import get_current_agent
from tickets.database import get_db
from tickets.models import ReplyTemplate
from tickets.template_engine import ALL_VARIABLES, extract_variables, fuzzy_search, render

router = APIRouter()


@router.get("/templates", response_class=HTMLResponse)
async def templates_page(
    request: Request,
    q: str = "",
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    from tickets.app import templates as tmpl
    result = await db.execute(
        select(ReplyTemplate).order_by(ReplyTemplate.use_count.desc(), ReplyTemplate.name)
    )
    all_templates = result.scalars().all()
    if q:
        all_templates = fuzzy_search(q, all_templates)

    return tmpl.TemplateResponse(request, "tickets/templates_list.html", {
        "templates": all_templates,
        "agent": agent,
        "q": q,
        "all_variables": ALL_VARIABLES,
    })


@router.get("/templates/new", response_class=HTMLResponse)
async def template_new_page(
    request: Request,
    agent=Depends(get_current_agent),
):
    from tickets.app import templates as tmpl
    return tmpl.TemplateResponse(request, "tickets/template_edit.html", {
        "tpl": None,
        "agent": agent,
        "all_variables": ALL_VARIABLES,
    })


@router.get("/templates/{tpl_id}/edit", response_class=HTMLResponse)
async def template_edit_page(
    request: Request,
    tpl_id: int,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    from tickets.app import templates as tmpl
    result = await db.execute(select(ReplyTemplate).where(ReplyTemplate.id == tpl_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404)
    return tmpl.TemplateResponse(request, "tickets/template_edit.html", {
        "tpl": tpl,
        "agent": agent,
        "all_variables": ALL_VARIABLES,
    })


@router.post("/api/templates")
async def create_template(
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    tpl = ReplyTemplate(
        name=body.get("name", ""),
        subject=body.get("subject"),
        body_html=body.get("body_html", ""),
        language=body.get("language", "zh-tw"),
        category=body.get("category"),
        search_keywords=body.get("search_keywords"),
        is_public=body.get("is_public", True),
        created_by=agent.id,
        variables=str(extract_variables(body.get("body_html", ""))),
    )
    db.add(tpl)
    await db.commit()
    return {"ok": True, "id": tpl.id}


@router.put("/api/templates/{tpl_id}")
async def update_template(
    tpl_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    result = await db.execute(select(ReplyTemplate).where(ReplyTemplate.id == tpl_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404)

    for field in ("name", "subject", "body_html", "language", "category", "search_keywords", "is_public"):
        if field in body:
            setattr(tpl, field, body[field])
    tpl.variables = str(extract_variables(tpl.body_html))
    await db.commit()
    return {"ok": True}


@router.delete("/api/templates/{tpl_id}")
async def delete_template(
    tpl_id: int,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    result = await db.execute(select(ReplyTemplate).where(ReplyTemplate.id == tpl_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404)
    await db.delete(tpl)
    await db.commit()
    return {"ok": True}


@router.get("/api/templates/search")
async def search_templates(
    q: str = "",
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    result = await db.execute(
        select(ReplyTemplate).where(ReplyTemplate.is_public == True).order_by(ReplyTemplate.use_count.desc())
    )
    all_tpls = result.scalars().all()
    matched = fuzzy_search(q, all_tpls, limit=8)
    return [{"id": t.id, "name": t.name, "category": t.category, "subject": t.subject, "body_html": t.body_html} for t in matched]


@router.post("/api/templates/{tpl_id}/render")
async def render_template(
    tpl_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(get_current_agent),
):
    body = await request.json()
    result = await db.execute(select(ReplyTemplate).where(ReplyTemplate.id == tpl_id))
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404)

    # Build context from request
    from sqlalchemy.orm import selectinload
    from tickets.models import Customer, Ticket
    ticket_id = body.get("ticket_id")
    context = {"agent": agent}
    if ticket_id:
        tr = await db.execute(
            select(Ticket).options(selectinload(Ticket.customer)).where(Ticket.id == ticket_id)
        )
        ticket = tr.scalar_one_or_none()
        if ticket:
            context["ticket"] = ticket
            context["customer"] = ticket.customer

    rendered = render(tpl.body_html, context)
    subject_rendered = render(tpl.subject or "", context)

    # Increment use count
    tpl.use_count += 1
    await db.commit()

    return {"body_html": rendered, "subject": subject_rendered}
