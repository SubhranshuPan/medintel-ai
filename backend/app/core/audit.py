"""Audit middleware — records every request to patient-data endpoints.

Why middleware rather than a per-endpoint call: a handler-level ``audit(...)``
is one line away from being forgotten on a new endpoint, and it cannot record
401/403 denials at all (the handler never runs). This intercepts by path prefix,
so a new route under an audited prefix is audited by default.

Endpoints may enrich the record by setting ``request.state.audit_detail`` (dict)
and ``request.state.audit_resource_id``.

Implemented as a raw ASGI middleware, not ``BaseHTTPMiddleware``: the latter
runs the downstream app in a spawned task, so ``call_next()`` can return before
the request's own DB session has actually torn down — two separate SQLite
connections in the test suite then deadlock each other (proven: the request's
own session and this middleware's session hit a 30s busy-timeout every time).
Awaiting the inner app directly, in this same task, guarantees the request's
own session is fully closed before we open ours.
"""

import uuid

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.db import AsyncSessionLocal
from app.core.security import decode_access_token
from app.models.audit import AuditLog

# Path prefixes (under /api/v1) whose requests touch patient-level data.
AUDITED_PREFIXES: tuple[str, ...] = ("/api/v1/datasets",)


def _resource_type(path: str) -> str:
    """Coarse resource type from the path (``/api/v1/datasets/...`` -> ``dataset``)."""
    parts = [p for p in path.split("/") if p]
    # ["api", "v1", "datasets", ...]
    return parts[2].rstrip("s") if len(parts) > 2 else "unknown"


def _resource_id(path: str) -> str | None:
    """The first UUID-shaped path segment, if any."""
    for part in path.split("/"):
        try:
            return str(uuid.UUID(part))
        except ValueError:
            continue
    return None


def _actor(request: Request) -> tuple[uuid.UUID | None, str | None]:
    """Best-effort actor from the bearer token — never raises."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None, None
    claims = decode_access_token(header.split(" ", 1)[1])
    if not claims or "sub" not in claims:
        return None, None
    try:
        return uuid.UUID(claims["sub"]), claims.get("role")
    except (ValueError, TypeError):
        return None, None


# ponytail: one extra DB session per audited request. Acceptable at portfolio
# scale; push the insert onto a background task/queue if write latency matters.
class AuditLogMiddleware:
    """Persist one ``AuditLog`` row per request to an audited path."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(AUDITED_PREFIXES):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        status_box: dict[str, int] = {}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_box["status_code"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        path = scope["path"]
        actor_id, actor_role = _actor(request)
        entry = AuditLog(
            actor_id=actor_id,
            actor_role=actor_role,
            action=scope["method"],
            resource_type=_resource_type(path),
            resource_id=getattr(request.state, "audit_resource_id", None) or _resource_id(path),
            path=path,
            status_code=status_box.get("status_code", 500),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:512] or None,
            detail=getattr(request.state, "audit_detail", None),
        )
        # Own session: the request session is already closed by the time we
        # regain control (we awaited the inner app directly, no spawned task),
        # and the audit write must not be rolled back with a failed request
        # transaction — a failed write attempt is precisely what we need on
        # record.
        async with AsyncSessionLocal() as session:
            session.add(entry)
            await session.commit()
