"""Narrow gateway operations exposed to opt-in plugin slash-command handlers.

Plugin commands normally receive only their raw argument string.  Commands that
need to create or switch a conversation must use the gateway's existing session
boundary methods instead of writing routing rows directly, so agent caches,
security state, ownership checks, and transcript persistence stay in sync.
"""

from __future__ import annotations

import dataclasses
import shlex
from typing import TYPE_CHECKING

from hermes_state import SessionDB

if TYPE_CHECKING:
    from gateway.session import SessionSource


class GatewayPluginCommandContext:
    """Safe session-bound operations for one plugin slash-command invocation.

    Instances are constructed by the gateway for the current inbound event only.
    They intentionally expose named session operations rather than the runner,
    which keeps profile plugins from bypassing the gateway's lifecycle and IDOR
    guards.
    """

    def __init__(self, runner, event, source: "SessionSource") -> None:
        self._runner = runner
        self._event = event
        self._source = source

    async def archive_and_reset(self, title: str) -> None:
        """Title the current conversation, persist it, then start a clean session.

        ``_handle_reset_command`` is the single gateway boundary for session
        rotation: it finalizes the prior transcript, clears cached agents and
        session-scoped state, and creates the new routing entry.
        """
        sanitized = SessionDB.sanitize_title(title)
        if not sanitized:
            raise ValueError("A story title is required.")
        entry = await self._runner.async_session_store.get_or_create_session(self._source)
        session_db = getattr(self._runner, "_session_db", None)
        if not entry or session_db is None or not await session_db.set_session_title(entry.session_id, sanitized):
            raise RuntimeError("Could not save the current story.")
        reset_event = dataclasses.replace(self._event, text="/new")
        await self._runner._handle_reset_command(reset_event)

    async def resume_own_session(self, selection: str = "") -> str:
        """List or resume only sessions the current source is allowed to access."""
        suffix = str(selection or "").strip()
        resume_text = "/resume" if not suffix else f"/resume {shlex.quote(suffix)}"
        resume_event = dataclasses.replace(self._event, text=resume_text)
        return await self._runner._handle_resume_command(resume_event)
