"""Login / logout routes."""
from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tickets.auth import COOKIE_NAME, create_session, verify_password, get_current_agent
from tickets.database import get_db
from tickets.models import Agent

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    from tickets.app import templates
    return templates.TemplateResponse(request, "tickets/login.html", {})


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.email == email.lower().strip(), Agent.is_active == True)
    )
    agent = result.scalar_one_or_none()

    if not agent or not verify_password(password, agent.password_hash):
        from tickets.app import templates
        return templates.TemplateResponse(
            request, "tickets/login.html", {"error": "帳號或密碼錯誤"}, status_code=401
        )

    token = await create_session(agent, db)
    resp = RedirectResponse(url="/tickets/inbox", status_code=303)
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=8 * 3600,
    )
    return resp


@router.post("/logout")
async def logout(response: Response):
    resp = RedirectResponse(url="/tickets/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp
