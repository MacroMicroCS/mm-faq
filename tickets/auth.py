"""Agent authentication — cookie-based sessions."""
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tickets.database import get_db
from tickets.models import Agent, AgentSession

SESSION_TTL_HOURS = 8
COOKIE_NAME = "ts"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


async def create_session(agent: Agent, db: AsyncSession) -> str:
    token = secrets.token_urlsafe(32)
    session = AgentSession(
        token=token,
        agent_id=agent.id,
        expires_at=datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS),
    )
    db.add(session)
    await db.commit()
    return token


async def get_current_agent(
    ts: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    if not ts:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await db.execute(
        select(AgentSession).where(AgentSession.token == ts)
    )
    session = result.scalar_one_or_none()

    if not session or session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    result = await db.execute(
        select(Agent).where(Agent.id == session.agent_id, Agent.is_active == True)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    return agent


async def require_admin(agent: Agent = Depends(get_current_agent)) -> Agent:
    if agent.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return agent
