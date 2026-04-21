"""In-memory collision detection — tracks which agents are viewing a ticket."""
import time
from collections import defaultdict

# { ticket_id: { agent_id: (agent_name, last_heartbeat_ts) } }
_PRESENCE: dict[int, dict[int, tuple[str, float]]] = defaultdict(dict)
TTL = 35  # seconds — JS sends heartbeat every 20s


def heartbeat(ticket_id: int, agent_id: int, agent_name: str):
    _PRESENCE[ticket_id][agent_id] = (agent_name, time.time())


def get_viewers(ticket_id: int, exclude_agent_id: int | None = None) -> list[dict]:
    now = time.time()
    viewers = []
    stale = []
    for aid, (name, ts) in _PRESENCE.get(ticket_id, {}).items():
        if now - ts > TTL:
            stale.append(aid)
        elif aid != exclude_agent_id:
            viewers.append({"agent_id": aid, "agent_name": name})
    for aid in stale:
        _PRESENCE[ticket_id].pop(aid, None)
    return viewers


def leave(ticket_id: int, agent_id: int):
    _PRESENCE.get(ticket_id, {}).pop(agent_id, None)
