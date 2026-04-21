"""Create the first agent account (run once to bootstrap)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tickets.database import AsyncSessionLocal, init_db
from tickets.models import Agent
from tickets.auth import hash_password
from sqlalchemy import select


async def main():
    await init_db()

    email = input("Email: ").strip().lower()
    name = input("姓名: ").strip()
    password = input("密碼: ").strip()
    role = input("角色 (admin/agent) [admin]: ").strip() or "admin"

    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(Agent).where(Agent.email == email))).scalar_one_or_none()
        if existing:
            print(f"❌ {email} 已存在")
            return

        agent = Agent(
            email=email,
            name=name,
            password_hash=hash_password(password),
            role=role,
        )
        db.add(agent)
        await db.commit()
        print(f"✅ 建立成功：{name} <{email}> ({role})")


if __name__ == "__main__":
    # TICKET_ENCRYPTION_KEY must be set — generate one if not exists
    if not os.environ.get("TICKET_ENCRYPTION_KEY"):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        print(f"\n⚠️  未設定 TICKET_ENCRYPTION_KEY，已產生新的 key：")
        print(f"   export TICKET_ENCRYPTION_KEY='{key}'")
        print(f"   請將此設定加入啟動環境（.env 或 shell profile）\n")
        os.environ["TICKET_ENCRYPTION_KEY"] = key

    asyncio.run(main())
