"""Controller helper: get the DI container from app state and run background work."""

from __future__ import annotations

import threading
from typing import Callable

from fastapi import Request


def get_container(request: Request):
    return request.app.state.container


def run_backend(fn: Callable[..., None], *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True, name="usecase-worker").start()
