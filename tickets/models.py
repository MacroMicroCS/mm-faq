"""SQLAlchemy ORM models — all phases defined upfront."""
import secrets
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tickets.database import Base


# ── Teams ─────────────────────────────────────────────────────────────────────

class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    agents: Mapped[list["Agent"]] = relationship("Agent", back_populates="team")


# ── Agents ────────────────────────────────────────────────────────────────────

class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="agent")  # admin | agent
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    team: Mapped["Team | None"] = relationship("Team", back_populates="agents")
    sessions: Mapped[list["AgentSession"]] = relationship("AgentSession", back_populates="agent", cascade="all, delete-orphan")


# ── Agent Sessions ─────────────────────────────────────────────────────────────

class AgentSession(Base):
    __tablename__ = "agent_sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: secrets.token_urlsafe(32))
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    agent: Mapped["Agent"] = relationship("Agent", back_populates="sessions")


# ── Customers ─────────────────────────────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("email_lower", name="uq_customer_email_lower"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    email_lower: Mapped[str] = mapped_column(String(255), nullable=False)  # always lowercased
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), default="zh-tw")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())

    tickets: Mapped[list["Ticket"]] = relationship("Ticket", back_populates="customer")


# ── Email Accounts ─────────────────────────────────────────────────────────────

class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    # IMAP
    imap_host: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_port: Mapped[int] = mapped_column(Integer, default=993)
    imap_user: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_password_enc: Mapped[str] = mapped_column(Text, nullable=False)  # Fernet encrypted
    # SMTP
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_user: Mapped[str] = mapped_column(String(255), nullable=False)
    smtp_password_enc: Mapped[str] = mapped_column(Text, nullable=False)
    # OAuth2 (Phase 2)
    auth_type: Mapped[str] = mapped_column(String(20), default="plain")  # plain | oauth2
    oauth_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Polling state
    last_uid: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tickets: Mapped[list["Ticket"]] = relationship("Ticket", back_populates="source_account")


# ── SLA Policies ──────────────────────────────────────────────────────────────

class SLAPolicy(Base):
    __tablename__ = "sla_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_response_hours: Mapped[int] = mapped_column(Integer, default=4)
    resolution_hours: Mapped[int] = mapped_column(Integer, default=24)
    applies_to_priority: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "urgent,high" or NULL=all
    business_hours_only: Mapped[bool] = mapped_column(Boolean, default=False)
    escalate_to_agent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("agents.id"), nullable=True)
    escalate_to_team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)


# ── Tickets ───────────────────────────────────────────────────────────────────

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open")      # open|pending|solved|closed
    priority: Mapped[str] = mapped_column(String(20), default="normal")  # low|normal|high|urgent
    channel: Mapped[str] = mapped_column(String(20), default="email")    # email|web|manual
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    assigned_agent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("agents.id"), nullable=True)
    assigned_team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("teams.id"), nullable=True)
    source_account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("email_accounts.id"), nullable=True)
    # Merge support
    merged_into_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tickets.id"), nullable=True)
    # Email threading
    email_message_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    email_thread_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    # SLA
    sla_policy_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sla_policies.id"), nullable=True)
    sla_first_response_due: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sla_resolution_due: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sla_first_responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    sla_escalated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # CSAT
    csat_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    csat_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    csat_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    csat_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    csat_survey_template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("csat_survey_templates.id"), nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    solved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="tickets")
    source_account: Mapped["EmailAccount | None"] = relationship("EmailAccount", back_populates="tickets")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="ticket", order_by="Message.created_at", cascade="all, delete-orphan")
    tags: Mapped[list["TicketTag"]] = relationship("TicketTag", back_populates="ticket", cascade="all, delete-orphan")
    activity: Mapped[list["TicketActivity"]] = relationship("TicketActivity", back_populates="ticket", order_by="TicketActivity.created_at", cascade="all, delete-orphan")
    reads: Mapped[list["TicketRead"]] = relationship("TicketRead", back_populates="ticket", cascade="all, delete-orphan")


# ── Messages ──────────────────────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    author_type: Mapped[str] = mapped_column(String(20), nullable=False)  # customer|agent|system
    author_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    # Template tracking
    template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("reply_templates.id"), nullable=True)
    template_variables: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    # AI tracking
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    # Email metadata
    email_message_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    email_in_reply_to: Mapped[str | None] = mapped_column(String(500), nullable=True)
    from_addr: Mapped[str | None] = mapped_column(String(500), nullable=True)
    to_addrs: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON array
    cc_addrs: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON array
    bcc_addrs: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="messages")
    attachments: Mapped[list["Attachment"]] = relationship("Attachment", back_populates="message", cascade="all, delete-orphan")


# ── Attachments ───────────────────────────────────────────────────────────────

class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("messages.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_inline: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    message: Mapped["Message"] = relationship("Message", back_populates="attachments")


# ── Tags ──────────────────────────────────────────────────────────────────────

class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#50e3c2")  # hex color


class TicketTag(Base):
    __tablename__ = "ticket_tags"

    ticket_id: Mapped[int] = mapped_column(Integer, ForeignKey("tickets.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), primary_key=True)

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="tags")
    tag: Mapped["Tag"] = relationship("Tag")


# ── Unread Tracking ───────────────────────────────────────────────────────────

class TicketRead(Base):
    __tablename__ = "ticket_reads"

    ticket_id: Mapped[int] = mapped_column(Integer, ForeignKey("tickets.id"), primary_key=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="reads")


# ── Reply Templates ───────────────────────────────────────────────────────────

class ReplyTemplate(Base):
    __tablename__ = "reply_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="zh-tw")
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    variables: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of variable names
    search_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("agents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())


# ── Automation Rules ──────────────────────────────────────────────────────────

class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    run_on: Mapped[str] = mapped_column(String(50), default="ticket_created")
    # run_on values: ticket_created | ticket_updated | message_received | time_based
    conditions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    actions: Mapped[str] = mapped_column(Text, nullable=False)     # JSON array
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    executions: Mapped[list["AutomationRuleExecution"]] = relationship("AutomationRuleExecution", back_populates="rule", cascade="all, delete-orphan")


class AutomationRuleExecution(Base):
    __tablename__ = "automation_rule_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("automation_rules.id"), nullable=False)
    ticket_id: Mapped[int] = mapped_column(Integer, ForeignKey("tickets.id"), nullable=False)
    actions_taken: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    rule: Mapped["AutomationRule"] = relationship("AutomationRule", back_populates="executions")


# ── Ticket Activity Log ───────────────────────────────────────────────────────

class TicketActivity(Base):
    __tablename__ = "ticket_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    agent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("agents.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # action values: created|status_changed|priority_changed|assigned|tag_added|tag_removed|merged|note_added
    field_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON for extra context
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="activity")


# ── CSAT Survey Templates ─────────────────────────────────────────────────────

class CSATSurveyTemplate(Base):
    __tablename__ = "csat_survey_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    delay_hours: Mapped[int] = mapped_column(Integer, default=24)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
