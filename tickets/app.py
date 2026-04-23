"""Ticket system FastAPI sub-application."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    from tickets.database import init_db
    await init_db()

    # Start IMAP polling background task
    from tickets.email_poller import poll_loop
    poller_task = asyncio.create_task(poll_loop())

    yield

    poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass


ticket_app = FastAPI(title="MacroMicro Ticket System", lifespan=lifespan)

# Static files at /tickets/static/tickets/
ticket_app.mount(
    "/static/tickets",
    StaticFiles(directory=str(BASE_DIR / "static" / "tickets")),
    name="ticket-static",
)

# Register routers
from tickets.routers import auth, customers, messages, settings, templates as tpl_router, tickets, uploads

ticket_app.include_router(auth.router)
ticket_app.include_router(tickets.router)
ticket_app.include_router(messages.router)
ticket_app.include_router(tpl_router.router)
ticket_app.include_router(customers.router)
ticket_app.include_router(settings.router)
ticket_app.include_router(uploads.router)


# Redirect /tickets/ → /tickets/inbox
from fastapi.responses import RedirectResponse

@ticket_app.get("/")
async def index():
    return RedirectResponse(url="/tickets/inbox")
