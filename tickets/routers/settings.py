"""Admin settings — email accounts, agents, tags, SLA."""
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tickets.auth import get_current_agent, hash_password, require_admin
from tickets.crypto import decrypt_value, encrypt_value
from tickets.database import get_db
from tickets.models import Agent, EmailAccount, SLAPolicy, Tag, Team

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(require_admin),
):
    from tickets.app import templates

    accounts = (await db.execute(select(EmailAccount))).scalars().all()
    agents = (await db.execute(select(Agent).order_by(Agent.created_at))).scalars().all()
    teams = (await db.execute(select(Team))).scalars().all()
    tags = (await db.execute(select(Tag))).scalars().all()
    sla_policies = (await db.execute(select(SLAPolicy))).scalars().all()

    return templates.TemplateResponse(request, "tickets/settings.html", {
        "accounts": accounts,
        "agents": agents,
        "teams": teams,
        "tags": tags,
        "sla_policies": sla_policies,
        "agent": agent,
        "encryption_key_set": bool(os.environ.get("TICKET_ENCRYPTION_KEY")),
    })


# ── Email Accounts ─────────────────────────────────────────────────────────────

@router.post("/api/settings/email-accounts")
async def create_email_account(
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(require_admin),
):
    body = await request.json()
    try:
        account = EmailAccount(
            label=body["label"],
            imap_host=body["imap_host"],
            imap_port=int(body.get("imap_port", 993)),
            imap_user=body["imap_user"],
            imap_password_enc=encrypt_value(body["imap_password"]),
            smtp_host=body["smtp_host"],
            smtp_port=int(body.get("smtp_port", 587)),
            smtp_user=body["smtp_user"],
            smtp_password_enc=encrypt_value(body["smtp_password"]),
            auth_type=body.get("auth_type", "plain"),
            is_active=body.get("is_active", True),
        )
        db.add(account)
        await db.commit()
        return {"ok": True, "id": account.id}
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e}")


@router.put("/api/settings/email-accounts/{account_id}")
async def update_email_account(
    account_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(require_admin),
):
    body = await request.json()
    result = await db.execute(select(EmailAccount).where(EmailAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404)

    for field in ("label", "imap_host", "imap_port", "smtp_host", "smtp_port", "is_active", "auth_type"):
        if field in body:
            setattr(account, field, body[field])
    if "imap_password" in body and body["imap_password"]:
        account.imap_password_enc = encrypt_value(body["imap_password"])
    if "smtp_password" in body and body["smtp_password"]:
        account.smtp_password_enc = encrypt_value(body["smtp_password"])
    await db.commit()
    return {"ok": True}


@router.delete("/api/settings/email-accounts/{account_id}")
async def delete_email_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    agent=Depends(require_admin),
):
    result = await db.execute(select(EmailAccount).where(EmailAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404)
    await db.delete(account)
    await db.commit()
    return {"ok": True}


@router.post("/api/settings/email-accounts/{account_id}/test")
async def test_email_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    agent=Depends(require_admin),
):
    """Test IMAP connection and return result."""
    import asyncio, imaplib, ssl
    result = await db.execute(select(EmailAccount).where(EmailAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404)

    def _test():
        try:
            password = decrypt_value(account.imap_password_enc)
            ctx = ssl.create_default_context()
            with imaplib.IMAP4_SSL(account.imap_host, account.imap_port, ssl_context=ctx) as imap:
                imap.login(account.imap_user, password)
                imap.select("INBOX")
                return {"ok": True, "message": "連線成功"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    return await asyncio.to_thread(_test)


# ── Agents ─────────────────────────────────────────────────────────────────────

@router.post("/api/settings/agents")
async def create_agent_account(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current=Depends(require_admin),
):
    body = await request.json()
    existing = (await db.execute(select(Agent).where(Agent.email == body["email"].lower()))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email 已存在")
    new_agent = Agent(
        email=body["email"].lower().strip(),
        name=body["name"],
        password_hash=hash_password(body["password"]),
        role=body.get("role", "agent"),
        team_id=body.get("team_id"),
    )
    db.add(new_agent)
    await db.commit()
    return {"ok": True, "id": new_agent.id}


@router.put("/api/settings/agents/{agent_id}")
async def update_agent(
    agent_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current=Depends(require_admin),
):
    body = await request.json()
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    a = result.scalar_one_or_none()
    if not a:
        raise HTTPException(status_code=404)
    for field in ("name", "role", "team_id", "is_active"):
        if field in body:
            setattr(a, field, body[field])
    if body.get("password"):
        a.password_hash = hash_password(body["password"])
    await db.commit()
    return {"ok": True}


# ── Tags ───────────────────────────────────────────────────────────────────────

@router.post("/api/settings/tags")
async def create_tag(
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(require_admin),
):
    body = await request.json()
    tag = Tag(name=body["name"], color=body.get("color", "#50e3c2"))
    db.add(tag)
    await db.commit()
    return {"ok": True, "id": tag.id}


@router.delete("/api/settings/tags/{tag_id}")
async def delete_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    agent=Depends(require_admin),
):
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404)
    await db.delete(tag)
    await db.commit()
    return {"ok": True}


# ── Teams ──────────────────────────────────────────────────────────────────────

@router.post("/api/settings/teams")
async def create_team(
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent=Depends(require_admin),
):
    body = await request.json()
    team = Team(name=body["name"])
    db.add(team)
    await db.commit()
    return {"ok": True, "id": team.id}
