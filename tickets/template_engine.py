"""Reply template variable substitution and fuzzy search."""
import difflib
import re
from typing import Any

# Available variables and their resolver functions
VARIABLE_RESOLVERS: dict[str, Any] = {
    "{{customer_name}}":   lambda ctx: (ctx["customer"].name or ctx["customer"].email.split("@")[0]) if ctx.get("customer") else "",
    "{{customer_email}}":  lambda ctx: ctx["customer"].email if ctx.get("customer") else "",
    "{{agent_name}}":      lambda ctx: ctx["agent"].name if ctx.get("agent") else "",
    "{{agent_email}}":     lambda ctx: ctx["agent"].email if ctx.get("agent") else "",
    "{{ticket_number}}":   lambda ctx: f"#{ctx['ticket'].number}" if ctx.get("ticket") else "",
    "{{ticket_subject}}":  lambda ctx: ctx["ticket"].subject if ctx.get("ticket") else "",
    "{{ticket_url}}":      lambda ctx: f"/tickets/{ctx['ticket'].id}" if ctx.get("ticket") else "",
    "{{csat_link}}":       lambda ctx: ctx.get("csat_url", ""),
    "{{today}}":           lambda ctx: __import__("datetime").date.today().strftime("%Y/%m/%d"),
}

ALL_VARIABLES = list(VARIABLE_RESOLVERS.keys())


def render(body: str, context: dict) -> str:
    """Replace all {{variable}} placeholders with resolved values."""
    for var, resolver in VARIABLE_RESOLVERS.items():
        if var in body:
            try:
                body = body.replace(var, str(resolver(context)))
            except Exception:
                pass
    return body


def fuzzy_search(query: str, templates: list, limit: int = 10) -> list:
    """Return templates sorted by relevance to query string."""
    if not query:
        return templates[:limit]

    query_lower = query.lower()
    scored = []
    for t in templates:
        score = 0
        name_lower = t.name.lower()
        # Exact match in name
        if query_lower in name_lower:
            score += 100
        # Word match
        for word in query_lower.split():
            if word in name_lower:
                score += 30
        # Fuzzy ratio on name
        ratio = difflib.SequenceMatcher(None, query_lower, name_lower).ratio()
        score += int(ratio * 50)
        # Search in keywords
        if t.search_keywords and query_lower in t.search_keywords.lower():
            score += 20
        # Search in body
        if query_lower in (t.body_html or "").lower():
            score += 10
        if score > 0:
            scored.append((score, t))

    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:limit]]


def extract_variables(body: str) -> list[str]:
    """Find all {{variable}} placeholders in a template body."""
    found = re.findall(r'\{\{[^}]+\}\}', body)
    return list(dict.fromkeys(found))  # deduplicated, order preserved
