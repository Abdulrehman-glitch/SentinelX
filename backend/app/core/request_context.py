"""Per-request correlation ID.

Threaded through logging via a contextvar rather than a request-scoped DI
parameter, so any code deep in a service call (not just route handlers) can
tag its log lines with the current request's ID without a signature change.
"""

from contextvars import ContextVar, Token

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id_var.get()


def set_request_id(request_id: str) -> Token:
    return _request_id_var.set(request_id)


def reset_request_id(token: Token) -> None:
    _request_id_var.reset(token)
